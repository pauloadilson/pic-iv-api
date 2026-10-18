# API meteorológica - HG Brasil

Coleta condições meteorológicas atuais de Álvares Machado/SP, persiste o JSON bruto e os campos TU (temperatura e umidade) em SQLite, evita duplicidade por localidade/hora e avalia continuidade das últimas 24 horas.

## Instalação

```bash
git switch -c feat/implementacao-api
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # no Windows, use: Copy-Item .env.example .env
```

Preencha `HG_BRASIL_KEY` e `DATABASE_URL` no `.env` e execute:

```bash
uvicorn app.main:app --reload
```

Documentação interativa: `http://127.0.0.1:8000/docs`.

### Autenticação por chave de API

Por padrão, os endpoints de coleta exigem o cabeçalho `X-API-Key`, com o valor
definido em `API_KEY`. Para desativar essa exigência (por exemplo, ao integrar
um backend que não possui a chave), defina a variável de ambiente abaixo:

```env
VALIDAR_API_KEY=false
```

No Vercel, configure `VALIDAR_API_KEY` nas Environment Variables do projeto e
faça um novo deploy. Para reativar a proteção, remova a variável ou defina-a
como `true` e configure `API_KEY`.

## Coleta manual

```bash
python -m app.coletor
```

Para coleta recorrente, o Vercel executa `GET /cron/coleta` uma vez por dia às 09:05 no horário de Brasília (12:05 UTC). O banco mantém uma única linha por `localidade_id + hora_referencia`.

## Endpoints

- `GET /health`
- `POST /coleta/executar`
- `GET /observacoes/24`
- `GET /observacoes/72`
- `GET /continuidade`

## Testes

```bash
pytest -q
```
