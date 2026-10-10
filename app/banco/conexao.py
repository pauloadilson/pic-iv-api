import sqlite3
from contextlib import contextmanager
from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS observacoes_meteorologicas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    localidade_id TEXT NOT NULL,
    cidade TEXT NOT NULL,
    latitude REAL,
    longitude REAL,
    timezone TEXT NOT NULL,
    instante_fonte TEXT NOT NULL,
    instante_coleta_utc TEXT NOT NULL,
    hora_referencia TEXT NOT NULL,
    temperatura_c REAL NOT NULL,
    umidade_pct REAL NOT NULL,
    resposta_original_json TEXT NOT NULL,
    origem TEXT NOT NULL DEFAULT 'hg_brasil',
    valido_modelo INTEGER NOT NULL DEFAULT 1,
    motivo_invalidacao TEXT,
    criado_em TEXT NOT NULL,
    UNIQUE (localidade_id, hora_referencia)
);
CREATE INDEX IF NOT EXISTS idx_obs_validas_hora
ON observacoes_meteorologicas (valido_modelo, hora_referencia);
"""

@contextmanager
def conectar():
    path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def inicializar_banco():
    with conectar() as conn:
        conn.executescript(SCHEMA)
