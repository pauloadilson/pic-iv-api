from urllib.parse import urlparse
import uuid

import httpx

from app.config import Settings, get_settings
from app.repositorios.observacoes import ultimas_validas
from app.servicos.continuidade import avaliar_continuidade


def _montar_urls_candidatas(settings: Settings) -> list[str]:
    """
    Monta a lista de URLs base da API de AM exclusivamente a partir das variáveis de ambiente
    (ML_API_URL, LOCAL_ML_API_URL e PORTA_ML_API), sem expor nem fixar URLs no código.
    """
    urls: list[str] = []

    if settings.ml_api_url and settings.ml_api_url.strip():
        urls.append(settings.ml_api_url.strip().rstrip("/"))

    if settings.local_ml_api_url and settings.local_ml_api_url.strip():
        base_local = settings.local_ml_api_url.strip().rstrip("/")
        if settings.porta_ml_api:
            parsed = urlparse(base_local)
            if parsed.scheme and parsed.hostname and parsed.port is None:
                caminho = parsed.path.rstrip("/")
                base_local = f"{parsed.scheme}://{parsed.hostname}:{settings.porta_ml_api}{caminho}"
        if base_local not in urls:
            urls.append(base_local)

    return urls


def _extrair_cidade_uf(cidade_bruta: str, padrao_cidade: str) -> tuple[str, str]:
    texto = (cidade_bruta or padrao_cidade or "Álvares Machado, SP").strip()
    if "," in texto:
        partes = [p.strip() for p in texto.split(",", 1)]
        return partes[0], (partes[1] or "SP")
    return texto, "SP"


def montar_payload_previsao_ml(
    registros_24h: list[dict],
    settings: Settings | None = None,
    include_summary: bool = True,
    include_indicators: bool = True,
) -> dict:
    """
    Constrói o payload padronizado de 24 observações horárias para envio à API de Aprendizagem de Máquina.
    """
    cfg = settings or get_settings()
    ultimo = registros_24h[-1] if registros_24h else {}

    woeid_str = str(ultimo.get("localidade_id") or cfg.hg_brasil_woeid or "458410").strip()
    try:
        woeid_val: int | str = int(woeid_str)
    except ValueError:
        woeid_val = woeid_str

    cidade, uf = _extrair_cidade_uf(
        str(ultimo.get("cidade") or ""),
        cfg.hg_brasil_city,
    )
    tz_name = str(ultimo.get("timezone") or cfg.app_timezone or "America/Sao_Paulo").strip()

    observations = [
        {
            "timestamp": reg["hora_referencia"],
            "temperature_c": float(reg["temperatura_c"]),
            "humidity_pct": float(reg["umidade_pct"]),
            "quality": "observed",
        }
        for reg in registros_24h
    ]

    return {
        "request_id": str(uuid.uuid4()),
        "location": {
            "id": f"hg-woeid-{woeid_val}",
            "woeid": woeid_val,
            "city": cidade,
            "state": uf,
            "country": "Brasil",
            "timezone": tz_name,
        },
        "source": {
            "provider": "hg_brasil",
            "dataset": "current_conditions_collected_hourly",
        },
        "observations": observations,
        "options": {
            "include_summary": include_summary,
            "include_indicators": include_indicators,
        },
    }


def obter_previsao_ml(
    include_summary: bool = True,
    include_indicators: bool = True,
) -> dict:
    """
    Avalia a continuidade das últimas 24 horas no banco e, caso esteja PRONTO,
    consulta a API de Aprendizagem de Máquina. Não expõe URLs internas no retorno.
    """
    continuidade = avaliar_continuidade()
    if continuidade.get("status") != "PRONTO":
        return {
            "status": "unavailable",
            "reason": continuidade.get("status", "INSUFICIENTE"),
            "message": (
                "A previsão por aprendizagem de máquina requer 24 observações horárias "
                f"consecutivas e válidas (status atual: {continuidade.get('status')}, "
                f"registros disponíveis: {continuidade.get('quantidade', 0)}/24)."
            ),
            "continuity": continuidade,
        }

    settings = get_settings()
    urls_candidatas = _montar_urls_candidatas(settings)
    if not urls_candidatas:
        return {
            "status": "unavailable",
            "reason": "ML_API_NOT_CONFIGURED",
            "message": "Serviço de aprendizagem de máquina não configurado no ambiente.",
            "continuity": continuidade,
        }

    registros_24h = ultimas_validas(24)
    payload = montar_payload_previsao_ml(
        registros_24h=registros_24h,
        settings=settings,
        include_summary=include_summary,
        include_indicators=include_indicators,
    )

    headers: dict[str, str] = {}
    if settings.ml_api_key and settings.ml_api_key.strip():
        headers["X-API-Key"] = settings.ml_api_key.strip()

    ultimo_erro_codigo = "ML_API_UNREACHABLE"
    ultimo_erro_msg = "Não foi possível obter resposta do serviço de aprendizagem de máquina."

    for base_url in urls_candidatas:
        endpoint = f"{base_url}/v1/forecast/24h"
        try:
            with httpx.Client(timeout=settings.ml_api_timeout_seconds) as client:
                resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 200:
                dados_ml = resp.json()
                if isinstance(dados_ml, dict) and dados_ml.get("status") == "success":
                    return dados_ml
            elif resp.status_code == 422:
                corpo_erro = resp.json() if resp.content else {}
                erro_obj = corpo_erro.get("error", {}) if isinstance(corpo_erro, dict) else {}
                ultimo_erro_codigo = erro_obj.get("code", "ML_VALIDATION_REJECTED")
                ultimo_erro_msg = erro_obj.get("message", "A janela de 24h foi rejeitada na validação do modelo.")
                break
            else:
                ultimo_erro_codigo = f"ML_API_HTTP_{resp.status_code}"
        except (httpx.HTTPError, ValueError):
            ultimo_erro_codigo = "ML_API_UNREACHABLE"

    return {
        "status": "unavailable",
        "reason": ultimo_erro_codigo,
        "message": ultimo_erro_msg,
        "continuity": continuidade,
    }

