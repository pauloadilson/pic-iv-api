from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
)

from app.seguranca.api_key import validar_api_key
from app.coleta.hg_brasil import ErroHGBrasil
from app.repositorios.observacoes import ultimas_validas
from app.servicos.coleta import executar_coleta
from app.servicos.continuidade import avaliar_continuidade
from app.servicos.meteorologia import obter_meteorologia_completa
from app.servicos.previsao_ml import obter_previsao_ml

router = APIRouter(
    dependencies=[
        Depends(validar_api_key),
    ],
)


@router.post("/coleta/executar")
def coletar():
    try:
        return executar_coleta()
    except ErroHGBrasil as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/meteorologia")
@router.get("/previsao")
def meteorologia(
    dias: int = Query(
        default=5,
        ge=1,
        le=10,
        description="Quantidade de dias de previsão do tempo (forecast) a retornar.",
    ),
    max_idade_minutos: int = Query(
        default=60,
        ge=1,
        le=1440,
        description="Idade máxima (em minutos) da última coleta no banco antes de consultar a HG Brasil ao vivo.",
    ),
    forcar_coleta: bool = Query(
        default=False,
        description="Se verdadeiro, força uma nova consulta na HG Brasil e atualiza o banco antes de retornar.",
    ),
):
    try:
        return obter_meteorologia_completa(
            dias_previsao=dias,
            max_idade_minutos=max_idade_minutos,
            forcar_coleta=forcar_coleta,
        )
    except ErroHGBrasil as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/previsao-ml")
def previsao_ml(
    include_summary: bool = Query(default=True),
    include_indicators: bool = Query(default=True),
):
    return obter_previsao_ml(
        include_summary=include_summary,
        include_indicators=include_indicators,
    )


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

