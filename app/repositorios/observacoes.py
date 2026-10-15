import json
from datetime import datetime, timezone

from sqlalchemy import select

from app.banco.conexao import get_engine
from app.banco.modelos import observacoes_meteorologicas


CAMPOS_ATUALIZAVEIS = {
    "cidade",
    "latitude",
    "longitude",
    "timezone",
    "instante_fonte",
    "instante_coleta_utc",
    "temperatura_c",
    "umidade_pct",
    "resposta_original_json",
}


def salvar_idempotente(obs: dict) -> dict:
    engine = get_engine()

    valores = {
        "localidade_id": obs["localidade_id"],
        "cidade": obs["cidade"],
        "latitude": obs["latitude"],
        "longitude": obs["longitude"],
        "timezone": obs["timezone"],
        "instante_fonte": obs["instante_fonte"],
        "instante_coleta_utc": obs["instante_coleta_utc"],
        "hora_referencia": obs["hora_referencia"],
        "temperatura_c": obs["temperatura_c"],
        "umidade_pct": obs["umidade_pct"],
        "resposta_original_json": json.dumps(
            obs["resposta_original"],
            ensure_ascii=False,
        ),
        "origem": "hg_brasil",
        "valido_modelo": True,
        "motivo_invalidacao": None,
        "criado_em": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    dialecto = engine.dialect.name

    if dialecto == "postgresql":
        from sqlalchemy.dialects.postgresql import insert

        comando = insert(
            observacoes_meteorologicas
        ).values(**valores)

    elif dialecto == "sqlite":
        from sqlalchemy.dialects.sqlite import insert

        comando = insert(
            observacoes_meteorologicas
        ).values(**valores)

    else:
        raise RuntimeError(
            f"Banco não suportado: {dialecto}"
        )

    atualizacoes = {
        campo: comando.excluded[campo]
        for campo in CAMPOS_ATUALIZAVEIS
    }

    comando = comando.on_conflict_do_update(
        index_elements=[
            observacoes_meteorologicas.c.localidade_id,
            observacoes_meteorologicas.c.hora_referencia,
        ],
        set_=atualizacoes,
    )

    with engine.begin() as conexao:
        conexao.execute(comando)

        consulta = (
            select(observacoes_meteorologicas)
            .where(
                observacoes_meteorologicas.c.localidade_id
                == obs["localidade_id"]
            )
            .where(
                observacoes_meteorologicas.c.hora_referencia
                == obs["hora_referencia"]
            )
        )

        registro = (
            conexao.execute(consulta)
            .mappings()
            .one()
        )

    return dict(registro)


def ultimas_validas(limit: int) -> list[dict]:
    if limit not in (24, 72):
        raise ValueError(
            "A janela deve ser 24 ou 72"
        )

    consulta_interna = (
        select(observacoes_meteorologicas)
        .where(
            observacoes_meteorologicas.c.valido_modelo.is_(
                True
            )
        )
        .order_by(
            observacoes_meteorologicas
            .c.hora_referencia.desc()
        )
        .limit(limit)
        .subquery()
    )

    consulta = (
        select(consulta_interna)
        .order_by(
            consulta_interna.c.hora_referencia.asc()
        )
    )

    engine = get_engine()

    with engine.connect() as conexao:
        registros = (
            conexao.execute(consulta)
            .mappings()
            .all()
        )

    return [
        dict(registro)
        for registro in registros
    ]