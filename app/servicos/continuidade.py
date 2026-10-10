from datetime import datetime, timedelta
from app.repositorios.observacoes import ultimas_validas

def avaliar_continuidade() -> dict:
    registros = ultimas_validas(24)
    base = {"quantidade": len(registros), "primeiro_horario": None, "ultimo_horario": None,
            "lacunas": [], "duplicidades": [], "fora_de_ordem": False, "campos_invalidos": []}
    if registros:
        base["primeiro_horario"] = registros[0]["hora_referencia"]
        base["ultimo_horario"] = registros[-1]["hora_referencia"]
    if len(registros) < 24:
        return {"status": "INSUFICIENTE", **base}

    horas = [datetime.fromisoformat(r["hora_referencia"]) for r in registros]
    base["fora_de_ordem"] = horas != sorted(horas)
    vistos = set()
    for i, (r, hora) in enumerate(zip(registros, horas)):
        if hora in vistos:
            base["duplicidades"].append(hora.isoformat())
        vistos.add(hora)
        if r["temperatura_c"] is None or not (-50 <= r["temperatura_c"] <= 60) or r["umidade_pct"] is None or not (0 <= r["umidade_pct"] <= 100):
            base["campos_invalidos"].append(r["id"])
        if i and hora - horas[i-1] != timedelta(hours=1):
            base["lacunas"].append({"apos": horas[i-1].isoformat(), "antes": hora.isoformat(), "intervalo_horas": (hora-horas[i-1]).total_seconds()/3600})
    pronto = not (base["lacunas"] or base["duplicidades"] or base["fora_de_ordem"] or base["campos_invalidos"])
    return {"status": "PRONTO" if pronto else "LACUNA", **base}
