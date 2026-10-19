import json
from datetime import datetime, timedelta, timezone

from app.coleta.hg_brasil import (
    ErroHGBrasil,
    _extrair_velocidade_vento_kmh,
    _float_or_none,
    extrair_dados_atuais,
    extrair_previsao,
)
from app.repositorios.observacoes import ultima_valida, ultimas_validas
from app.servicos.coleta import executar_coleta


def _carregar_payload_original(registro: dict) -> dict:
    bruto = registro.get("resposta_original_json")
    if not bruto:
        return {}
    if isinstance(bruto, dict):
        return bruto
    try:
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else {}
    except (TypeError, ValueError):
        return {}


def _registro_defasado(
    registro: dict,
    max_idade_minutos: int,
) -> bool:
    instante_coleta_str = registro.get("instante_coleta_utc")
    if not instante_coleta_str:
        return True

    try:
        instante_coleta = datetime.fromisoformat(instante_coleta_str)
    except ValueError:
        return True

    if instante_coleta.tzinfo is None:
        instante_coleta = instante_coleta.replace(tzinfo=timezone.utc)

    agora_utc = datetime.now(timezone.utc)
    limite = timedelta(minutes=max_idade_minutos)
    return (agora_utc - instante_coleta) > limite


def _resumir_janela(registros: list[dict], horas_janela: int) -> dict:
    if not registros:
        return {
            "janela_horas": horas_janela,
            "quantidade_observacoes": 0,
            "primeiro_horario": None,
            "ultimo_horario": None,
            "precipitacao_acumulada_mm": 0.0,
            "temperatura_max_c": None,
            "temperatura_min_c": None,
            "temperatura_media_c": None,
            "umidade_max_pct": None,
            "umidade_min_pct": None,
            "umidade_media_pct": None,
            "vento_max_kmh": None,
        }

    temperaturas: list[float] = []
    umidades: list[float] = []
    chuvas: list[float] = []
    ventos: list[float] = []

    for reg in registros:
        temp = _float_or_none(reg.get("temperatura_c"))
        if temp is not None:
            temperaturas.append(temp)

        umid = _float_or_none(reg.get("umidade_pct"))
        if umid is not None:
            umidades.append(umid)

        payload = _carregar_payload_original(reg)
        results = payload.get("results") if isinstance(payload, dict) else None
        if isinstance(results, dict):
            chuva = _float_or_none(results.get("rain"))
            if chuva is not None and chuva >= 0:
                chuvas.append(chuva)

            vento = _extrair_velocidade_vento_kmh(results.get("wind_speedy"))
            if vento is not None and vento >= 0:
                ventos.append(vento)

    precipitacao_total = round(sum(chuvas), 2) if chuvas else 0.0

    return {
        "janela_horas": horas_janela,
        "quantidade_observacoes": len(registros),
        "primeiro_horario": registros[0].get("hora_referencia"),
        "ultimo_horario": registros[-1].get("hora_referencia"),
        "precipitacao_acumulada_mm": precipitacao_total,
        "temperatura_max_c": round(max(temperaturas), 2) if temperaturas else None,
        "temperatura_min_c": round(min(temperaturas), 2) if temperaturas else None,
        "temperatura_media_c": (
            round(sum(temperaturas) / len(temperaturas), 2)
            if temperaturas
            else None
        ),
        "umidade_max_pct": round(max(umidades), 2) if umidades else None,
        "umidade_min_pct": round(min(umidades), 2) if umidades else None,
        "umidade_media_pct": (
            round(sum(umidades) / len(umidades), 2)
            if umidades
            else None
        ),
        "vento_max_kmh": round(max(ventos), 2) if ventos else None,
    }


def calcular_resumo_historico() -> dict:
    registros_72h = ultimas_validas(72)
    registros_24h = registros_72h[-24:] if len(registros_72h) > 24 else registros_72h

    resumo_24h = _resumir_janela(registros_24h, 24)
    resumo_72h = _resumir_janela(registros_72h, 72)

    return {
        "precipitacao_acumulada_24h_mm": resumo_24h["precipitacao_acumulada_mm"],
        "precipitacao_acumulada_72h_mm": resumo_72h["precipitacao_acumulada_mm"],
        "janela_24h": resumo_24h,
        "janela_72h": resumo_72h,
    }


def obter_meteorologia_completa(
    dias_previsao: int = 5,
    max_idade_minutos: int = 60,
    forcar_coleta: bool = False,
) -> dict:
    registro = ultima_valida()
    origem_dados = "banco"

    precisa_coletar = (
        forcar_coleta
        or registro is None
        or _registro_defasado(registro, max_idade_minutos)
    )

    if precisa_coletar:
        try:
            registro = executar_coleta()
            origem_dados = "coleta_ao_vivo"
        except ErroHGBrasil:
            if registro is None:
                raise
            origem_dados = "banco_defasado_fallback"

    payload_original = _carregar_payload_original(registro)
    dados_atuais = extrair_dados_atuais(
        payload_original,
        registro_banco=registro,
    )
    previsao = extrair_previsao(
        payload_original,
        dias=dias_previsao,
    )
    historico = calcular_resumo_historico()
    results = payload_original.get("results")
    if not isinstance(results, dict):
        results = {}

    return {
        "localidade_id": registro["localidade_id"],
        "cidade": registro["cidade"],
        "latitude": registro["latitude"],
        "longitude": registro["longitude"],
        "timezone": registro["timezone"],
        "hora_referencia": registro["hora_referencia"],
        "instante_fonte": registro["instante_fonte"],
        "instante_coleta_utc": registro["instante_coleta_utc"],
        "origem_dados": origem_dados,
        "atual": dados_atuais,
        "previsao": previsao,
        "historico": historico,
        "results": results,
    }

