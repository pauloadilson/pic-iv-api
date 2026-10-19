from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.coleta.hg_brasil import (
    ErroHGBrasil,
    extrair_dados_atuais,
    extrair_previsao,
)
from app.main import app
from app.repositorios.observacoes import salvar_idempotente
from app.servicos import meteorologia as servico_meteorologia


def _payload_hg_completo(chuva_atual: float = 2.5):
    return {
        "by": "woeid",
        "valid_key": True,
        "results": {
            "woeid": 458410,
            "temp": 26,
            "date": "18/10/2026",
            "time": "14:00",
            "condition_code": "28",
            "description": "Tempo parcialmente nublado",
            "currently": "dia",
            "city": "Álvares Machado, SP",
            "city_name": "Álvares Machado",
            "timezone": "-03:00",
            "humidity": 68,
            "cloudiness": 40,
            "rain": chuva_atual,
            "wind_speedy": "14.5 km/h",
            "wind_direction": 135,
            "wind_cardinal": "SE",
            "sunrise": "05:52 am",
            "sunset": "06:30 pm",
            "moon_phase": "crescente",
            "forecast": [
                {
                    "date": "18/10",
                    "weekday": "Dom",
                    "max": 31,
                    "min": 19,
                    "cloudiness": 40,
                    "rain": 4.5,
                    "rain_probability": 60,
                    "wind_speedy": "14.5 km/h",
                    "description": "Sol com pancadas à tarde",
                    "condition": "rain",
                },
                {
                    "date": "19/10",
                    "weekday": "Seg",
                    "max": 28,
                    "min": 18,
                    "cloudiness": 75,
                    "rain": 18.0,
                    "rain_probability": 85,
                    "wind_speedy": "19.2 km/h",
                    "description": "Chuva moderada",
                    "condition": "rain",
                },
                {
                    "date": "20/10",
                    "weekday": "Ter",
                    "max": 25,
                    "min": 17,
                    "cloudiness": 60,
                    "rain": 8.0,
                    "rain_probability": 70,
                    "wind_speedy": "12.0 km/h",
                    "description": "Chuva isolada",
                    "condition": "rain",
                },
                {
                    "date": "21/10",
                    "weekday": "Qua",
                    "max": 29,
                    "min": 16,
                    "cloudiness": 15,
                    "rain": 0.0,
                    "rain_probability": 10,
                    "wind_speedy": "9.0 km/h",
                    "description": "Tempo limpo",
                    "condition": "clear_day",
                },
            ],
        },
    }


def _criar_observacao(
    instante_coleta: datetime,
    hora_ref: datetime,
    temp: float = 26.0,
    umidade: float = 68.0,
    chuva_mm: float = 2.5,
) -> dict:
    return {
        "localidade_id": "458410",
        "cidade": "Álvares Machado, SP",
        "latitude": -22.079,
        "longitude": -51.471,
        "timezone": "-03:00",
        "instante_fonte": hora_ref.isoformat(),
        "instante_coleta_utc": instante_coleta.isoformat(),
        "hora_referencia": hora_ref.isoformat(),
        "temperatura_c": temp,
        "umidade_pct": umidade,
        "resposta_original": _payload_hg_completo(chuva_atual=chuva_mm),
    }


def test_extrai_dados_atuais_e_previsao():
    payload = _payload_hg_completo(chuva_atual=3.2)

    atuais = extrair_dados_atuais(payload)
    assert atuais["temperatura_c"] == 26.0
    assert atuais["temperatura_max_c"] == 31.0
    assert atuais["temperatura_min_c"] == 19.0
    assert atuais["umidade_pct"] == 68.0
    assert atuais["chuva_mm"] == 3.2
    assert atuais["probabilidade_chuva_pct"] == 60.0
    assert atuais["velocidade_vento_kmh"] == 14.5
    assert atuais["direcao_vento_cardeal"] == "SE"
    assert atuais["condicao"] == "Tempo parcialmente nublado"

    previsao_3_dias = extrair_previsao(payload, dias=3)
    assert len(previsao_3_dias) == 3
    assert previsao_3_dias[0]["rotulo_dia"] == "Hoje"
    assert previsao_3_dias[1]["rotulo_dia"] == "Amanhã"
    assert previsao_3_dias[2]["rotulo_dia"] == "Ter"
    assert previsao_3_dias[1]["chuva_mm"] == 18.0
    assert previsao_3_dias[1]["probabilidade_chuva_pct"] == 85.0


def test_obter_meteorologia_usa_banco_quando_recente(monkeypatch):
    agora = datetime.now(timezone.utc)
    hora_ref = agora.replace(minute=0, second=0, microsecond=0)
    salvar_idempotente(
        _criar_observacao(
            instante_coleta=agora - timedelta(minutes=10),
            hora_ref=hora_ref,
            chuva_mm=4.0,
        )
    )

    chamou_coleta = False

    def _coleta_nao_deve_ser_chamada():
        nonlocal chamou_coleta
        chamou_coleta = True
        raise AssertionError("Não deveria consultar a HG Brasil se o banco está atualizado")

    monkeypatch.setattr(
        servico_meteorologia,
        "executar_coleta",
        _coleta_nao_deve_ser_chamada,
    )

    resultado = servico_meteorologia.obter_meteorologia_completa(
        dias_previsao=3,
        max_idade_minutos=60,
    )

    assert not chamou_coleta
    assert resultado["origem_dados"] == "banco"
    assert resultado["atual"]["chuva_mm"] == 4.0
    assert len(resultado["previsao"]) == 3
    assert resultado["historico"]["precipitacao_acumulada_72h_mm"] == 4.0


def test_obter_meteorologia_faz_fallback_para_banco_se_coleta_falhar(monkeypatch):
    agora = datetime.now(timezone.utc)
    antigo = agora - timedelta(hours=3)
    hora_ref = antigo.replace(minute=0, second=0, microsecond=0)
    salvar_idempotente(
        _criar_observacao(
            instante_coleta=antigo,
            hora_ref=hora_ref,
            chuva_mm=1.5,
        )
    )

    def _coleta_com_erro():
        raise ErroHGBrasil("Limite de requisições atingido")

    monkeypatch.setattr(
        servico_meteorologia,
        "executar_coleta",
        _coleta_com_erro,
    )

    resultado = servico_meteorologia.obter_meteorologia_completa(
        dias_previsao=3,
        max_idade_minutos=60,
    )

    assert resultado["origem_dados"] == "banco_defasado_fallback"
    assert resultado["atual"]["chuva_mm"] == 1.5


def test_endpoint_meteorologia_acumulado_72h(monkeypatch):
    monkeypatch.setenv("VALIDAR_API_KEY", "false")
    from app.config import get_settings
    get_settings.cache_clear()

    agora = datetime.now(timezone.utc)
    base_hora = agora.replace(minute=0, second=0, microsecond=0)

    # Insere 3 observações: 2 nas últimas 24h (2.0mm cada) e 1 há 48h (5.0mm)
    salvar_idempotente(
        _criar_observacao(
            instante_coleta=agora - timedelta(hours=48),
            hora_ref=base_hora - timedelta(hours=48),
            chuva_mm=5.0,
        )
    )
    salvar_idempotente(
        _criar_observacao(
            instante_coleta=agora - timedelta(hours=1),
            hora_ref=base_hora - timedelta(hours=1),
            chuva_mm=2.0,
        )
    )
    salvar_idempotente(
        _criar_observacao(
            instante_coleta=agora - timedelta(minutes=5),
            hora_ref=base_hora,
            chuva_mm=2.0,
        )
    )

    client = TestClient(app)
    resp = client.get("/meteorologia?dias=3")
    assert resp.status_code == 200

    dados = resp.json()
    assert dados["origem_dados"] == "banco"
    assert len(dados["previsao"]) == 3
    # Como temos apenas 3 registros no banco, tanto a janela de 24 quanto a de 72 pegam os 3 registros (soma = 9.0mm)
    assert dados["historico"]["precipitacao_acumulada_72h_mm"] == 9.0
    assert dados["results"]["city"] == "Álvares Machado, SP"

