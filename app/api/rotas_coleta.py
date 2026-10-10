from fastapi import APIRouter, HTTPException
from app.coleta.hg_brasil import ErroHGBrasil
from app.repositorios.observacoes import ultimas_validas
from app.servicos.coleta import executar_coleta
from app.servicos.continuidade import avaliar_continuidade

router = APIRouter()

@router.post("/coleta/executar")
def coletar():
    try:
        return executar_coleta()
    except ErroHGBrasil as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

@router.get("/observacoes/{janela}")
def observacoes(janela: int):
    if janela not in (24, 72):
        raise HTTPException(status_code=400, detail="A janela deve ser 24 ou 72")
    itens = ultimas_validas(janela)
    return {"janela": janela, "quantidade": len(itens),
            "primeiro_horario": itens[0]["hora_referencia"] if itens else None,
            "ultimo_horario": itens[-1]["hora_referencia"] if itens else None,
            "observacoes": itens}

@router.get("/continuidade")
def continuidade():
    return avaliar_continuidade()
