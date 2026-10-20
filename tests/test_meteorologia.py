from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.coleta.hg_brasil import (
    ErroHGBrasil,
    avaliar_risco_granizo,
    detectar_granizo,
    detectar_tempestade,
    extrair_dados_atuais,
    extrair_previsao,
)
from app.main import app
from app.repositorios.observacoes import salvar_idempotente
from app.servicos import meteorologia as servico_meteorologia


def _payload_hg_completo(
    chuva_atual: float = 2.5,
    condition_code: str = "28",
    condition_slug: str = "cloudly_day",
    description: str = "Tempo parcialmente nublado",
):
    return {
        "by": "woeid",
        "valid_key": True,
        "results": {
            "woeid": 458410,
            "temp": 26,
            "date": "18/10/2026",
            "time": "14:00",
            "condition_code": condition_code,
            "condition_slug": condition_slug,
            "description": description,
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
                    "max": 32,
                    "min": 18,
                    "cloudiness": 75,
                    "rain": 18.0,
                    "rain_probability": 85,
                    "wind_speedy": "19.2 km/h",
                    "description": "Tempestade isolada",
                    "condition": "storm",
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
                    "description": "Chuva e granizo",
                    "condition": "hail",
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
    condition_code: str = "28",
    condition_slug: str = "cloudly_day",
    description: str = "Tempo parcialmente nublado",
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
        "resposta_original": _payload_hg_completo(
            chuva_atual=chuva_mm,
            condition_code=condition_code,
            condition_slug=condition_slug,
            description=description,
        ),
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
    assert atuais["granizo_detectado"] is False
    assert atuais["tempestade_detectada"] is False

    previsao_3_dias = extrair_previsao(payload, dias=3)
    assert len(previsao_3_dias) == 3
    assert previsao_3_dias[0]["rotulo_dia"] == "Hoje"
    assert previsao_3_dias[0]["risco_granizo_nivel"] == "baixo"
    assert previsao_3_dias[1]["rotulo_dia"] == "Amanhã"
    assert previsao_3_dias[1]["tempestade_detectada"] is True
    assert previsao_3_dias[1]["risco_granizo_nivel"] == "moderado"
    assert previsao_3_dias[2]["rotulo_dia"] == "Ter"
    assert previsao_3_dias[2]["granizo_detectado"] is True
    assert previsao_3_dias[2]["risco_granizo_nivel"] == "critico"


def test_deteccao_e_classificacao_granizo_e_tempestade():
    assert detectar_granizo(condition_slug="hail") is True
    assert detectar_granizo(condition_code="17") is True
    assert detectar_granizo(condition_code="35") is True
    assert detectar_granizo(description="Pancadas de chuva com Granizo") is True
    assert detectar_granizo(condition_slug="rain", condition_code="28", description="Chuva") is False

    assert detectar_tempestade(condition_slug="storm") is True
    assert detectar_tempestade(condition_code="3") is True
    assert detectar_tempestade(condition_code="4") is True
    assert detectar_tempestade(description="Tempestades severas") is True
    assert detectar_tempestade(condition_slug="clear_day", condition_code="27", description="Limpo") is False

    # 1. Risco Crítico (condition_code 17 / hail)
    risco_critico = avaliar_risco_granizo(
        {"granizo_detectado": True, "tempestade_detectada": False, "temperatura_c": 24.0, "probabilidade_chuva_pct": 80.0},
        [],
    )
    assert risco_critico["nivel"] == "critico"
    assert risco_critico["level"] == "danger"
    assert risco_critico["granizo_detectado"] is True

    # 2. Risco Moderado (storm + calor >= 30°C + prob_chuva >= 70%)
    risco_moderado = avaliar_risco_granizo(
        {"granizo_detectado": False, "tempestade_detectada": True, "temperatura_c": 29.0, "temperatura_max_c": 32.0, "probabilidade_chuva_pct": 75.0},
        [],
    )
    assert risco_moderado["nivel"] == "moderado"
    assert risco_moderado["level"] == "warning"
    assert risco_moderado["gatilho_convectivo"] is True

    # 3. Baixo Risco
    risco_baixo = avaliar_risco_granizo(
        {"granizo_detectado": False, "tempestade_detectada": False, "temperatura_c": 25.0, "temperatura_max_c": 28.0, "probabilidade_chuva_pct": 30.0},
        [],
    )
    assert risco_baixo["nivel"] == "baixo"
    assert risco_baixo["level"] == "success"
    assert risco_baixo["gatilho_convectivo"] is False


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
    assert resultado["risco_granizo"]["nivel"] == "baixo"
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

    # Insere 3 observações: 1 há 48h com granizo (código 35), 1 há 1h com tempestade (código 4) e 1 atual
    salvar_idempotente(
        _criar_observacao(
            instante_coleta=agora - timedelta(hours=48),
            hora_ref=base_hora - timedelta(hours=48),
            chuva_mm=5.0,
            condition_code="35",
            condition_slug="hail",
            description="Chuva e granizo",
        )
    )
    salvar_idempotente(
        _criar_observacao(
            instante_coleta=agora - timedelta(hours=1),
            hora_ref=base_hora - timedelta(hours=1),
            chuva_mm=2.0,
            condition_code="4",
            condition_slug="storm",
            description="Tempestades",
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
    assert dados["historico"]["precipitacao_acumulada_72h_mm"] == 9.0
    assert dados["historico"]["ocorrencias_granizo_72h"] == 1
    assert dados["historico"]["ocorrencias_tempestade_72h"] == 1
    assert dados["risco_granizo"]["nivel"] == "baixo"
    assert dados["results"]["city"] == "Álvares Machado, SP"
