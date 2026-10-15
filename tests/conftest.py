import pytest

from app.banco.conexao import get_engine
from app.config import get_settings


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    banco_teste = tmp_path / "teste.db"

    monkeypatch.setenv(
        "HG_BRASIL_KEY",
        "chave-teste",
    )

    monkeypatch.setenv(
        "DATABASE_URL",
        f"sqlite:///{banco_teste.as_posix()}",
    )

    get_settings.cache_clear()
    get_engine.cache_clear()

    from app.banco.conexao import inicializar_banco

    inicializar_banco()

    yield

    engine = get_engine()
    engine.dispose()

    get_engine.cache_clear()
    get_settings.cache_clear()