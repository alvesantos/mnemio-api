# Mnemio Backend

## Tecnologias

- Python 3
- FastAPI
- Uvicorn (ASGI server)

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

## Rodando

```bash
./venv/bin/uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`. Endpoint `GET /` retorna `{"message": "Hello API"}`.
