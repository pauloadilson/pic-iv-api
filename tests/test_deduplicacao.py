from app.repositorios.observacoes import salvar_idempotente, ultimas_validas

def obs(temp=25):
    return {"localidade_id":"458410","cidade":"Alvares Machado, SP","latitude":None,"longitude":None,"timezone":"America/Sao_Paulo","instante_fonte":"2026-10-10T14:10:00-03:00","instante_coleta_utc":"2026-10-10T17:10:00+00:00","hora_referencia":"2026-10-10T14:00:00-03:00","temperatura_c":temp,"umidade_pct":50,"resposta_original":{"ok":True}}

def test_upsert_nao_duplica():
    salvar_idempotente(obs(25)); salvar_idempotente(obs(26))
    itens = ultimas_validas(24)
    assert len(itens) == 1
    assert itens[0]["temperatura_c"] == 26
