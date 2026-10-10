import json
from datetime import datetime, timezone
from app.banco.conexao import conectar

CAMPOS_PUBLICOS = """id, localidade_id, cidade, latitude, longitude, timezone,
instante_fonte, instante_coleta_utc, hora_referencia, temperatura_c,
umidade_pct, origem, valido_modelo, motivo_invalidacao, criado_em"""

def salvar_idempotente(obs: dict) -> dict:
    agora = datetime.now(timezone.utc).isoformat()
    sql = """
    INSERT INTO observacoes_meteorologicas (
      localidade_id, cidade, latitude, longitude, timezone, instante_fonte,
      instante_coleta_utc, hora_referencia, temperatura_c, umidade_pct,
      resposta_original_json, criado_em
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(localidade_id, hora_referencia) DO UPDATE SET
      cidade=excluded.cidade, latitude=excluded.latitude, longitude=excluded.longitude,
      timezone=excluded.timezone, instante_fonte=excluded.instante_fonte,
      instante_coleta_utc=excluded.instante_coleta_utc,
      temperatura_c=excluded.temperatura_c, umidade_pct=excluded.umidade_pct,
      resposta_original_json=excluded.resposta_original_json
    """
    values = (obs["localidade_id"], obs["cidade"], obs["latitude"], obs["longitude"],
              obs["timezone"], obs["instante_fonte"], obs["instante_coleta_utc"],
              obs["hora_referencia"], obs["temperatura_c"], obs["umidade_pct"],
              json.dumps(obs["resposta_original"], ensure_ascii=False), agora)
    with conectar() as conn:
        conn.execute(sql, values)
        row = conn.execute(f"SELECT {CAMPOS_PUBLICOS} FROM observacoes_meteorologicas WHERE localidade_id=? AND hora_referencia=?",
                           (obs["localidade_id"], obs["hora_referencia"])).fetchone()
    return dict(row)

def ultimas_validas(limit: int) -> list[dict]:
    if limit not in (24, 72):
        raise ValueError("A janela deve ser 24 ou 72")
    sql = f"""SELECT {CAMPOS_PUBLICOS} FROM (
      SELECT {CAMPOS_PUBLICOS} FROM observacoes_meteorologicas
      WHERE valido_modelo=1 ORDER BY hora_referencia DESC LIMIT ?
    ) ORDER BY hora_referencia ASC"""
    with conectar() as conn:
        return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
