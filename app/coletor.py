import json
import sys
from datetime import datetime, timezone

from app.banco.conexao import inicializar_banco
from app.servicos.coleta import executar_coleta


def main() -> int:
    inicio = datetime.now(timezone.utc)

    print(
        f"[COLETA] Início: {inicio.isoformat()}",
        flush=True,
    )

    try:
        inicializar_banco()
        observacao = executar_coleta()

        print(
            json.dumps(
                observacao,
                ensure_ascii=False,
                indent=2,
            ),
            flush=True,
        )

        fim = datetime.now(timezone.utc)

        print(
            f"[COLETA] Concluída: {fim.isoformat()}",
            flush=True,
        )

        return 0

    except Exception as exc:
        print(
            "[COLETA] Falha: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
            flush=True,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())