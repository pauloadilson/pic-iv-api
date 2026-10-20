from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import Settings
from app.repositorios.observacoes import salvar_idempotente
from app.servicos.previsao_ml import (
    _montar_urls_candidatas,
    montar_payload_previsao_ml,
    obter_previsao_ml,
)


def _popular_24_horas():
    tz = ZoneInfo("America/Sao_Paulo")
    base = datetime(2026, 10, 18, 14, 0, 0, tzinfo=tz)
    for i in range(24):
        dt = base + timedelta(hours=i)
        salvar_idempotente(
            {
                "localidade_id": "458410",
                "cidade": "Álvares Machado, SP",
                "latitude": -22.08,
                "longitude": -51.47,
                "timezone": "America/Sao_Paulo",
                "instante_fonte": dt.isoformat(),
                "instante_coleta_utc": dt.isoformat(),
                "hora_referencia": dt.isoformat(),
                "temperatura_c": 24.0 + (i % 6),
                "umidade_pct": 60.0 + (i % 10),
                "resposta_original": {"results": {"temp": 25, "humidity": 65}},
            }
        )


def test_previsao_ml_insuficiente_sem_24_registros():
    res = obter_previsao_ml()
    assert res["status"] == "unavailable"
    assert res["reason"] == "INSUFICIENTE"
    assert res["continuity"]["quantidade"] < 24


def test_montar_urls_candidatas_com_porta():
    cfg = Settings(
        hg_brasil_key="dummy",
        database_url="sqlite:///:memory:",
        ml_api_url=None,
        local_ml_api_url="http://localhost",
        porta_ml_api=8001,
    )
    urls = _montar_urls_candidatas(cfg)
    assert len(urls) == 1
    assert urls[0].endswith(":8001")


def test_montar_payload_previsao_ml_estrutura_completa():
    _popular_24_horas()
    from app.repositorios.observacoes import ultimas_validas

    regs = ultimas_validas(24)
    payload = montar_payload_previsao_ml(regs)

    assert "request_id" in payload
    assert payload["location"]["id"] == "hg-woeid-458410"
    assert payload["location"]["woeid"] == 458410
    assert payload["location"]["city"] == "Álvares Machado"
    assert payload["location"]["state"] == "SP"
    assert payload["location"]["timezone"] == "America/Sao_Paulo"
    assert payload["source"]["provider"] == "hg_brasil"
    assert len(payload["observations"]) == 24
    assert payload["options"]["include_summary"] is True
    assert payload["options"]["include_indicators"] is True

