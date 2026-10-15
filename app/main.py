from fastapi import FastAPI
from app.api.rotas_coleta import router
from app.banco.conexao import get_engine

app = FastAPI(
    title="API Meteorologica - Alvares Machado",
    version="0.1.0",
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