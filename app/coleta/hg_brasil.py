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
