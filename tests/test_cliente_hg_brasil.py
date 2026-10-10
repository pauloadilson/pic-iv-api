from app.coleta.hg_brasil import ClienteHGBrasil
from app.config import get_settings

def test_normaliza_resposta():
    payload = {"valid_key": True, "results": {"woeid": 458410, "city_name": "Alvares Machado, SP", "timezone": "America/Sao_Paulo", "date": "10/10/2026", "time": "14:37", "temp": 28, "humidity": 52}}
    obs = ClienteHGBrasil(get_settings()).normalizar(payload)
    assert obs["hora_referencia"].endswith("14:00:00-03:00")
    assert obs["temperatura_c"] == 28.0
