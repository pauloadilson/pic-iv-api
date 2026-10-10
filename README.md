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

Preencha `HG_BRASIL_KEY` no `.env` e execute:

```bash
uvicorn app.main:app --reload
```

Documentação interativa: `http://127.0.0.1:8000/docs`.

## Coleta manual

```bash
python -m app.coletor
```

Para coleta recorrente, agende esse comando uma vez por hora, preferencialmente alguns minutos após a virada. O banco mantém uma única linha por `localidade_id + hora_referencia`.

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
