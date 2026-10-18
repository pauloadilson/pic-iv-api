import pytest
from fastapi import HTTPException

from app.config import get_settings
from app.seguranca.api_key import validar_api_key


def configurar_ambiente(monkeypatch, *, validar: str, api_key: str | None):
    monkeypatch.setenv("VALIDAR_API_KEY", validar)
    if api_key is None:
        monkeypatch.setenv("API_KEY", "")
    else:
        monkeypatch.setenv("API_KEY", api_key)
    get_settings.cache_clear()


def test_nao_exige_chave_quando_validacao_desativada(monkeypatch):
    configurar_ambiente(monkeypatch, validar="false", api_key=None)

    assert validar_api_key(None) is None


def test_exige_chave_quando_validacao_ativada(monkeypatch):
    configurar_ambiente(monkeypatch, validar="true", api_key="chave-teste")

    with pytest.raises(HTTPException) as erro:
        validar_api_key(None)

    assert erro.value.status_code == 401


def test_informa_configuracao_incompleta(monkeypatch):
    configurar_ambiente(monkeypatch, validar="true", api_key=None)

    with pytest.raises(HTTPException) as erro:
        validar_api_key("qualquer-chave")

    assert erro.value.status_code == 503
