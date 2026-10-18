import hmac
from typing import Annotated

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings


api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="APIKey",
    description=(
        "Chave utilizada para autorizar o acesso "
        "aos endpoints protegidos."
    ),
    auto_error=False,
)


def validar_api_key(
    chave_recebida: Annotated[
        str | None,
        Security(api_key_header),
    ],
) -> str | None:
    settings = get_settings()

    if not settings.validar_api_key:
        return None

    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A autenticação por chave de API não está configurada",
        )

    if chave_recebida is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API não informada",
            headers={
                "WWW-Authenticate": "APIKey",
            },
        )

    if not hmac.compare_digest(
        chave_recebida,
        settings.api_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API inválida",
            headers={
                "WWW-Authenticate": "APIKey",
            },
        )

    return chave_recebida