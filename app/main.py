from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.rotas_coleta import router
from app.banco.conexao import get_engine, inicializar_banco


@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_banco()
    yield


app = FastAPI(
    title="API Meteorológica - Álvares Machado",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health")
def health():
    engine = get_engine()

    return {
        "status": "ok",
        "aplicacao": "api-meteorologica",
        "database": engine.dialect.name,
    }