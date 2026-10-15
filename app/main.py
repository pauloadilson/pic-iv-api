from fastapi import FastAPI
from app.api.rotas_coleta import router

app = FastAPI(
    title="API Meteorologica - Alvares Machado",
    version="0.1.0",
)

app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "aplicacao": "api-meteorologica",
    }