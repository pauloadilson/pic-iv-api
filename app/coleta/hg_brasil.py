from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import re
import unicodedata

import httpx
from app.config import Settings

def normalizar_texto(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", valor)
    texto_sem_acentos = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    return " ".join(texto_sem_acentos.casefold().split())

def interpretar_timezone(valor: str):
    """
    Interpreta tanto identificadores IANA, como America/Sao_Paulo,
    quanto deslocamentos UTC fixos, como -03:00.
    """
    valor = valor.strip()

    deslocamento = re.fullmatch(
        r"(?P<sinal>[+-])(?P<horas>\d{2}):(?P<minutos>\d{2})",
        valor,
    )

    if deslocamento:
        horas = int(deslocamento.group("horas"))
        minutos = int(deslocamento.group("minutos"))

        if horas > 23 or minutos > 59:
            raise ValueError(
                f"Deslocamento UTC inválido: {valor}"
            )

        total = timedelta(hours=horas, minutes=minutos)

        if deslocamento.group("sinal") == "-":
            total = -total

        return timezone(total)

    return ZoneInfo(valor)

class ErroHGBrasil(RuntimeError):
    pass

class ClienteHGBrasil:
    URL = "https://api.hgbrasil.com/weather"

    def __init__(self, config: Settings):
        self.config = config

    def consultar(self) -> dict:
        params = {"key": self.config.hg_brasil_key, "woeid": self.config.hg_brasil_woeid}
        try:
            with httpx.Client(timeout=self.config.hg_brasil_timeout_seconds) as client:
                response = client.get(self.URL, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ErroHGBrasil(f"Falha na consulta meteorologica: {type(exc).__name__}") from exc
        return self.normalizar(payload)

    def normalizar(self, payload: dict) -> dict:
        if payload.get("valid_key") is False:
            raise ErroHGBrasil("A HG Brasil rejeitou a chave de integracao")
        results = payload.get("results")
        if not isinstance(results, dict):
            raise ErroHGBrasil("Resposta sem objeto results")

        woeid = str(results.get("woeid", ""))
        if woeid != self.config.hg_brasil_woeid:
            raise ErroHGBrasil(f"WOEID inesperado: {woeid or 'ausente'}")
        city = str(
            results.get("city_name")
            or results.get("city")
            or ""
        ).strip()

        expected = self.config.hg_brasil_city.split(",")[0].strip()

        cidade_normalizada = normalizar_texto(city)
        cidade_esperada_normalizada = normalizar_texto(expected)

        if cidade_esperada_normalizada not in cidade_normalizada:
            raise ErroHGBrasil(
                "Cidade inesperada: "
                f"recebida={city or 'ausente'}; "
                f"esperada={expected}"
            )

        tz_name = str(
            results.get("timezone")
            or self.config.app_timezone
        ).strip()

        try:
            tz = interpretar_timezone(tz_name)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ErroHGBrasil(
                f"Timezone inválido recebido da fonte: {tz_name}"
            ) from exc

        date_value, time_value = results.get("date"), results.get("time")
        if not date_value or not time_value:
            raise ErroHGBrasil("Resposta sem data/hora da fonte")
        instante = None
        for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M"):
            try:
                instante = datetime.strptime(f"{date_value} {time_value}", fmt).replace(tzinfo=tz)
                break
            except ValueError:
                pass
        if instante is None:
            raise ErroHGBrasil("Formato de data/hora da fonte nao reconhecido")
        
        agora_fonte = datetime.now(tz)
        limite_futuro = agora_fonte + timedelta(minutes=15)

        if instante > limite_futuro:
            raise ErroHGBrasil(
                "Horário da fonte está excessivamente no futuro: "
                f"fonte={instante.isoformat()}; "
                f"coleta={agora_fonte.isoformat()}"
            )
        
        try:
            temp = float(results["temp"])
            humidity = float(results["humidity"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ErroHGBrasil("Temperatura ou umidade invalida") from exc
        if not (-50 <= temp <= 60) or not (0 <= humidity <= 100):
            raise ErroHGBrasil("Temperatura ou umidade fora da faixa esperada")

        coleta_utc = datetime.now(timezone.utc)
        return {
            "localidade_id": woeid,
            "cidade": city,
            "latitude": _float_or_none(results.get("latitude")),
            "longitude": _float_or_none(results.get("longitude")),
            "timezone": tz_name,
            "instante_fonte": instante.isoformat(),
            "instante_coleta_utc": coleta_utc.isoformat(),
            "hora_referencia": instante.replace(minute=0, second=0, microsecond=0).isoformat(),
            "temperatura_c": temp,
            "umidade_pct": humidity,
            "resposta_original": payload,
        }

def _float_or_none(value):
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _extrair_velocidade_vento_kmh(valor) -> float | None:
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(valor))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None


def extrair_dados_atuais(
    payload: dict,
    registro_banco: dict | None = None,
) -> dict:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, dict):
        results = {}

    forecast = results.get("forecast")
    hoje = (
        forecast[0]
        if isinstance(forecast, list) and forecast and isinstance(forecast[0], dict)
        else {}
    )

    temp = _float_or_none(results.get("temp"))
    if temp is None and registro_banco is not None:
        temp = _float_or_none(registro_banco.get("temperatura_c"))

    umidade = _float_or_none(results.get("humidity"))
    if umidade is None and registro_banco is not None:
        umidade = _float_or_none(registro_banco.get("umidade_pct"))

    chuva_mm = _float_or_none(results.get("rain"))
    if chuva_mm is None:
        chuva_mm = 0.0

    prob_chuva = _float_or_none(hoje.get("rain_probability"))
    if prob_chuva is None:
        prob_chuva = 0.0

    vento_formatado = results.get("wind_speedy")
    velocidade_vento_kmh = _extrair_velocidade_vento_kmh(vento_formatado)

    return {
        "temperatura_c": temp,
        "temperatura_max_c": _float_or_none(hoje.get("max")),
        "temperatura_min_c": _float_or_none(hoje.get("min")),
        "umidade_pct": umidade,
        "chuva_mm": chuva_mm,
        "probabilidade_chuva_pct": prob_chuva,
        "nebulosidade_pct": _float_or_none(results.get("cloudiness")),
        "velocidade_vento_kmh": velocidade_vento_kmh,
        "vento_formatado": vento_formatado,
        "direcao_vento_graus": _float_or_none(results.get("wind_direction")),
        "direcao_vento_cardeal": results.get("wind_cardinal"),
        "condicao": results.get("description"),
        "codigo_condicao": (
            str(results["condition_code"])
            if results.get("condition_code") is not None
            else None
        ),
        "condicao_slug": results.get("condition_slug"),
        "periodo": results.get("currently"),
        "nascer_do_sol": results.get("sunrise"),
        "por_do_sol": results.get("sunset"),
        "fase_lua": results.get("moon_phase"),
    }


def extrair_previsao(
    payload: dict,
    dias: int | None = None,
) -> list[dict]:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, dict):
        return []

    forecast = results.get("forecast")
    if not isinstance(forecast, list):
        return []

    itens_brutos = [item for item in forecast if isinstance(item, dict)]
    if dias is not None and dias > 0:
        itens_brutos = itens_brutos[:dias]

    previsao_normalizada = []
    for idx, item in enumerate(itens_brutos):
        weekday = item.get("weekday")
        rotulo_dia = (
            "Hoje"
            if idx == 0
            else ("Amanhã" if idx == 1 else weekday)
        )
        temp_max = _float_or_none(item.get("max"))
        temp_min = _float_or_none(item.get("min"))
        chuva_mm = _float_or_none(item.get("rain"))
        if chuva_mm is None:
            chuva_mm = 0.0
        prob_chuva = _float_or_none(item.get("rain_probability"))
        if prob_chuva is None:
            prob_chuva = 0.0
        nebulosidade = _float_or_none(item.get("cloudiness"))
        vento_fmt = item.get("wind_speedy")

        previsao_normalizada.append(
            {
                "data": item.get("date"),
                "dia_semana": weekday,
                "rotulo_dia": rotulo_dia,
                "temperatura_max_c": temp_max,
                "temperatura_min_c": temp_min,
                "chuva_mm": chuva_mm,
                "probabilidade_chuva_pct": prob_chuva,
                "nebulosidade_pct": nebulosidade,
                "velocidade_vento_kmh": _extrair_velocidade_vento_kmh(vento_fmt),
                "vento_formatado": vento_fmt,
                "condicao": item.get("description"),
                "condicao_slug": item.get("condition"),
                # Chaves originais HG Brasil para compatibilidade direta com o Backend
                "date": item.get("date"),
                "weekday": weekday,
                "max": temp_max,
                "min": temp_min,
                "rain": chuva_mm,
                "rain_probability": prob_chuva,
                "cloudiness": nebulosidade,
                "wind_speedy": vento_fmt,
                "description": item.get("description"),
                "condition": item.get("condition"),
            }
        )

    return previsao_normalizada

