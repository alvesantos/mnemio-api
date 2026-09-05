# Mnemio Backend

## Tecnologias

- Python 3
- FastAPI
- Uvicorn (ASGI server)
- SQLAlchemy + PostgreSQL (psycopg 3)
- Alembic (migrations)
- PyJWT + bcrypt (autenticação)
- Docker Compose (Postgres local)

## Setup

```bash
docker compose up -d                   # sobe Postgres local (porta 5433)
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp .env.example .env                   # define SECRET_KEY e DATABASE_URL
./venv/bin/alembic upgrade head        # cria as tabelas
```

`.env.example` já vem com `DATABASE_URL` apontando pro Postgres do `docker-compose.yml` (`mnemio`/`mnemio` em `localhost:5433`). Gera um `SECRET_KEY` próprio:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
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
