import json
from app.banco.conexao import inicializar_banco
from app.servicos.coleta import executar_coleta

if __name__ == "__main__":
    inicializar_banco()
    print(json.dumps(executar_coleta(), ensure_ascii=False, indent=2))
