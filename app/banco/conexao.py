from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.banco.modelos import metadata
from app.config import get_settings


def normalizar_database_url(url: str) -> str:
    """
    Garante o uso do driver Psycopg 3 para URLs PostgreSQL.
    """

    if url.startswith("postgres://"):
        return url.replace(
            "postgres://",
            "postgresql+psycopg://",
            1,
        )

    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return url


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    database_url = normalizar_database_url(
        settings.database_url
    )

    argumentos = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    if database_url.startswith("sqlite"):
        argumentos["connect_args"] = {
            "check_same_thread": False,
        }

        prefixo = "sqlite:///"

        if database_url.startswith(prefixo):
            caminho = database_url[len(prefixo):]

            if caminho and caminho != ":memory:":
                Path(caminho).parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

    return create_engine(
        database_url,
        **argumentos,
    )


def inicializar_banco() -> None:
    engine = get_engine()
    metadata.create_all(engine)