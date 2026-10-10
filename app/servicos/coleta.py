from app.config import get_settings
from app.coleta.hg_brasil import ClienteHGBrasil
from app.repositorios.observacoes import salvar_idempotente

def executar_coleta() -> dict:
    observacao = ClienteHGBrasil(get_settings()).consultar()
    return salvar_idempotente(observacao)
