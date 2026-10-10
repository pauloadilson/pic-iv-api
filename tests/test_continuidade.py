from datetime import datetime, timedelta, timezone
from app.repositorios.observacoes import salvar_idempotente
from app.servicos.continuidade import avaliar_continuidade

def test_24_horas_consecutivas_pronto():
    inicio = datetime(2026, 10, 1, tzinfo=timezone.utc)
    for i in range(24):
        h = inicio + timedelta(hours=i)
        salvar_idempotente({"localidade_id":"458410","cidade":"Alvares Machado, SP","latitude":None,"longitude":None,"timezone":"UTC","instante_fonte":h.isoformat(),"instante_coleta_utc":h.isoformat(),"hora_referencia":h.isoformat(),"temperatura_c":25,"umidade_pct":50,"resposta_original":{"i":i}})
    assert avaliar_continuidade()["status"] == "PRONTO"
