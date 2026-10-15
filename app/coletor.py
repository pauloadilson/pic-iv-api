import json
from datetime import datetime, timezone

from app.banco.conexao import inicializar_banco
from app.servicos.coleta import executar_coleta


def main() -> None:
    print(
        "[COLETA] Início: "
        f"{datetime.now(timezone.utc).isoformat()}",
        flush=True,
    )

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

    print(
        "[COLETA] Concluída: "
        f"{datetime.now(timezone.utc).isoformat()}",
        flush=True,
    )


if __name__ == "__main__":
    main()