# Mnemio Backend

## Tecnologias

- Python 3
- FastAPI
- Uvicorn (ASGI server)
- SQLAlchemy + SQLite
- Alembic (migrations)
- PyJWT + bcrypt (autenticação)

## Setup

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env   # define SECRET_KEY
```

## Migrations

Schema do banco é versionado via Alembic (não usa `create_all`).

```bash
./venv/bin/alembic upgrade head              # aplica migrations pendentes
./venv/bin/alembic revision --autogenerate -m "descrição"   # gera nova migration após mudar models.py
./venv/bin/alembic downgrade -1              # desfaz última migration
```

Roda `alembic upgrade head` sempre que puxar mudanças ou antes de rodar o servidor pela primeira vez.

## Rodando

```bash
./venv/bin/uvicorn app.main:app --reload
```

API disponível em `http://localhost:8000`.

## Endpoints

- `GET /` — `{"message": "Hello API"}`
- `POST /auth/register` — `{name, email, password}` → cria usuário, retorna token
- `POST /auth/login` — `{email, password}` → retorna token
- `GET /auth/me` — requer `Authorization: Bearer <token>`, retorna dados do usuário
