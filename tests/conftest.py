import pytest
from app.config import get_settings

@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("HG_BRASIL_KEY", "chave-teste")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'teste.db'}")
    get_settings.cache_clear()
    from app.banco.conexao import inicializar_banco
    inicializar_banco()
    yield
    get_settings.cache_clear()
