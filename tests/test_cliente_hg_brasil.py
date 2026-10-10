from datetime import timedelta
from app.coleta.hg_brasil import ClienteHGBrasil
from app.config import get_settings
from app.coleta.hg_brasil import interpretar_timezone

def test_normaliza_resposta():
    payload = {
        "valid_key": True,
        "results": {
            "woeid": 458410,
            "city_name": "Álvares Machado",
            "timezone": "-03:00",
            "date": "10/10/2026",
            "time": "14:37",
            "temp": 28,
            "humidity": 52,
        },
    }

    obs = ClienteHGBrasil(get_settings()).normalizar(payload)

    assert obs["hora_referencia"].endswith(
        "14:00:00-03:00"
    )
    assert obs["temperatura_c"] == 28.0
    assert obs["umidade_pct"] == 52.0
    assert obs["timezone"] == "-03:00"



def test_interpreta_deslocamento_utc_fixo():
    tz = interpretar_timezone("-03:00")

    assert tz.utcoffset(None) == -timedelta(hours=3)