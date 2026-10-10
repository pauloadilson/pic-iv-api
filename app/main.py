from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.rotas_coleta import router
from app.banco.conexao import inicializar_banco

@asynccontextmanager
async def lifespan(app: FastAPI):
    inicializar_banco()
    yield

app = FastAPI(title="API Meteorologica - Alvares Machado", version="0.1.0", lifespan=lifespan)
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}
