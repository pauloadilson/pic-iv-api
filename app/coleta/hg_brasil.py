from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import httpx
from app.config import Settings

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
        city = str(results.get("city_name") or results.get("city") or "").strip()
        expected = self.config.hg_brasil_city.split(",")[0].strip().casefold()
        if expected not in city.casefold():
            raise ErroHGBrasil(f"Cidade inesperada: {city or 'ausente'}")

        tz_name = str(results.get("timezone") or self.config.app_timezone)
        try:
            tz = ZoneInfo(tz_name)
        except Exception as exc:
            raise ErroHGBrasil(f"Timezone invalido: {tz_name}") from exc

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
