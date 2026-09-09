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

### Chaves das fontes externas

A busca de mídias consulta APIs externas em tempo real. Sem as chaves o backend
sobe normalmente — só a busca do tipo correspondente devolve vazio, com aviso no log.

| Variável | Fonte | Como obter |
|---|---|---|
| `TMDB_API_READ_ACCESS_TOKEN` | TMDB (filmes, séries, doramas) | conta em themoviedb.org → Settings → API → "API Read Access Token" (v4) |
| `GOOGLE_BOOKS_API_KEY` | Google Books (livros) | Google Cloud Console → APIs → Books API → credenciais. Opcional na API, mas sem chave a quota é por IP e estoura rápido |

**Anime não tem busca externa.** A AniList desativou a API pública, então
`/busca?tipo=animes` responde `400` e o app manda direto para o cadastro manual.
O client continua pronto em `app/media_sources/anilist.py`: para religar, basta
devolver a linha `"animes": anilist.CLIENT` ao dicionário `CLIENTS` de
`app/media_sources/__init__.py`.

Passo a passo de deploy, e o que fazer quando o faturamento do GCP voltar:
[`docs/DEPLOY.md`](docs/DEPLOY.md). Como a busca e o cache funcionam por dentro:
[`docs/busca-e-cache-de-midias.md`](docs/busca-e-cache-de-midias.md).

Os ajustes de timeout, TTL de cache e países que contam como dorama estão
comentados em `.env.example`.

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
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --reload
```

`--host 0.0.0.0` é obrigatório pra testar do celular/outro dispositivo na rede — sem isso o servidor só aceita conexão de `localhost`. API fica em `http://localhost:8000` (ou `http://<seu-ip-local>:8000` pra outros dispositivos; roda `hostname -I` pra ver o IP).

## Testes

```bash
./venv/bin/pytest -v
```

Usa SQLite em memória (não toca no Postgres). Cada CRUD tem cobertura de: criar (com/sem nota), validação de nota (0-5) e título, listar, buscar, atualizar, deletar, 404 e isolamento entre usuários.

## Endpoints

- `GET /` — `{"message": "Hello API"}`
- `POST /auth/register` — `{name, email, password}` → cria usuário, retorna token
- `POST /auth/login` — `{email, password}` → retorna token
- `GET /auth/me` — requer `Authorization: Bearer <token>`, retorna dados do usuário

CRUD idêntico pra cada recurso abaixo (todos exigem `Authorization: Bearer <token>`, itens são isolados por usuário):

- `/livros`
- `/series`
- `/filmes`
- `/animes`
- `/doramas`

Para cada um: `POST /` (`{title, rating?}`), `GET /` (lista), `GET /{id}`, `PUT /{id}` (`{title?, rating?}`), `DELETE /{id}`. `rating` vai de 0 a 5.

No `POST /` dá pra mandar `media_ref` (`{source, external_id}`) para vincular o
item ao catálogo — ver abaixo.

### Busca e catálogo de mídias

- `GET /busca?q=duna&tipo=filmes&limit=20` — busca em tempo real na fonte externa
  (TMDB ou Google Books, conforme o tipo). Não persiste nada. Cada resultado
  traz `cached`/`media_id` quando o item já está no banco. Se a fonte estiver fora,
  responde 200 com o que houver em cache e o header `X-Search-Degraded: true`.
- `GET /midias/{tipo}/{source}/{external_id}` — detalhe de um item. Serve do cache
  quando existe; senão busca na fonte e grava em background.

O catálogo (`media_items`) é global e cacheado **sob demanda**: um item só entra no
banco quando alguém abre o detalhe ou o adiciona à própria lista. Nada de importar
catálogo inteiro. Detalhes em [`docs/busca-e-cache-de-midias.md`](docs/busca-e-cache-de-midias.md).
