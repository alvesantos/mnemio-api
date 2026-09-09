# Operação e deploy

Tudo que precisa ser feito para colocar a API no ar, na ordem. Estado verificado em
2026-09-09.

## Onde cada coisa mora

| Peça | Onde |
|---|---|
| API | Cloud Run, serviço `mnemio-api`, região `southamerica-east1`, projeto `mnemio-prod-f25c` |
| URL | `https://mnemio-api-cj354xkp5a-rj.a.run.app` (e `https://mnemio-api-599928340489.southamerica-east1.run.app` — as duas servem o mesmo serviço) |
| Banco | Neon, `ep-super-queen-acnl08yu-pooler.sa-east-1.aws.neon.tech`, Postgres 16 |
| Segredos | Secret Manager: `mnemio-secret-key`, `mnemio-database-url` |
| Service account do Cloud Run | `mnemio-api@mnemio-prod-f25c.iam.gserviceaccount.com` |
| Repositórios | API: `alvesantos/mnemio-api` · App: `alvesantos/mnemio` |
| App | EAS, projeto `280c1240-748e-4d9a-a2e9-345313c736f0` |

---

# Parte 1 — Quando o GCP voltar

## 1.1 Por que parou

A conta de faturamento do projeto foi fechada porque o **perfil de pagamentos do Google
entrou em verificação de identidade**. Com a conta fechada, nada billable roda: o Cloud Run
para de servir e o Secret Manager recusa qualquer chamada.

Linha do tempo, tirada dos logs do Cloud Run:

```
2026-09-06 19:04 UTC  último deploy bem-sucedido
2026-09-07 23:31 UTC  último request atendido (200 em /privacidade)
2026-09-08 14:26 UTC  primeiro "The request failed because billing is disabled for this project"
```

Como diagnosticar de novo, se acontecer:

```bash
TOKEN=$(gcloud auth print-access-token)
curl -s -H "Authorization: Bearer $TOKEN" \
  https://cloudbilling.googleapis.com/v1/billingAccounts/01EEA0-786E70-9AB451
```

`"open": false` é conta fechada. `"open": true` e a API ainda fora significa outro problema
— vá para os logs (§3.3).

**O banco no Neon não é afetado por isso.** Ele é de outro provedor: continua no ar com
todos os dados durante a parada inteira.

## 1.2 Resolver a verificação

O Google pede dois envios em https://payments.google.com:

1. **Foto da forma de pagamento** — o cartão cadastrado no perfil. Precisa aparecer o nome e
   os 4 últimos dígitos; cubra os outros 12. Nunca envie o verso com o CVV.
2. **Documento de identidade com foto** — RG, CNH ou passaporte. **O nome tem que ser igual
   ao do cartão**, senão é recusado.

A análise leva de 1 a 3 dias úteis e o resultado chega por e-mail.

## 1.3 Depois de aprovado

```bash
# 1. conta reaberta?
TOKEN=$(gcloud auth print-access-token)
curl -s -H "Authorization: Bearer $TOKEN" \
  https://cloudbilling.googleapis.com/v1/billingAccounts/01EEA0-786E70-9AB451
# precisa mostrar "open": true

# 2. a API volta sozinha, sem deploy nenhum
curl -s https://mnemio-api-cj354xkp5a-rj.a.run.app/
# esperado: {"message":"Hello API"}
```

Se a conta reabriu mas a API demora, espere alguns minutos: a propagação não é instantânea.

Voltando o `{"message":"Hello API"}`, o app está de pé exatamente como estava antes da
parada — ainda **sem** as funcionalidades novas. Elas entram na Parte 2.

## 1.4 Evitar que aconteça de novo

Crie um orçamento com alerta em
https://console.cloud.google.com/billing/budgets — R$ 10 com aviso em 50% já resolve. O
custo real tende a zero: o Cloud Run tem free tier e o banco está fora do GCP.

E não deixe o projeto parado por semanas com faturamento desligado: as imagens no Artifact
Registry são as primeiras a serem apagadas.

---

# Parte 2 — Colocar a busca de mídias no ar

Só precisa ser feito uma vez. Depois, deploy é o comando da §3.1 e mais nada.

## 2.1 Pegar as chaves

São duas. Anime não precisa de nenhuma porque saiu do app.

### TMDB — filmes, séries e doramas

1. Entre em https://www.themoviedb.org/ e acesse **Settings → API**
   (https://www.themoviedb.org/settings/api)
2. Se ainda não tiver chave, clique em **Request an API Key** → tipo **Developer** → aceite
   os termos e preencha o formulário (nome "Mnemio", uso pessoal serve)
3. A página mostra dois valores. Copie o **segundo**:
   - `API Key (v3 auth)` — **não é esse**
   - **`API Read Access Token (v4 auth)`** — é esse, um JWT longo começando com `eyJ`

Gratuito, liberado na hora.

### Google Books — livros

Sem chave a quota é compartilhada por IP e já vem estourada (`429 Quota exceeded`), então
ela não é opcional na prática.

1. Ative a API:
   https://console.cloud.google.com/apis/library/books.googleapis.com?project=mnemio-prod-f25c
2. Crie a credencial:
   https://console.cloud.google.com/apis/credentials?project=mnemio-prod-f25c
   → **Criar credenciais → Chave de API**
3. Clique em **Restringir chave**:
   - *Restrições de API* → marque apenas **Books API**
   - *Restrições de aplicativo* → **Nenhuma** (quem chama é o Cloud Run, que não tem IP fixo)

Quota gratuita: 1.000 requisições/dia. Acompanhe em
https://console.cloud.google.com/apis/api/books.googleapis.com/quotas?project=mnemio-prod-f25c

## 2.2 Guardar as chaves no Secret Manager

```bash
gcloud config set project mnemio-prod-f25c

gcloud secrets create mnemio-tmdb-token --replication-policy=automatic
printf '%s' 'COLE_O_TOKEN_V4' | gcloud secrets versions add mnemio-tmdb-token --data-file=-

gcloud secrets create mnemio-google-books-key --replication-policy=automatic
printf '%s' 'COLE_A_CHAVE' | gcloud secrets versions add mnemio-google-books-key --data-file=-
```

`printf` em vez de `echo` de propósito: `echo` acrescenta `\n` ao valor, e o token iria com
quebra de linha no fim — a API responderia 401 e a busca ficaria degradada sem motivo
aparente.

Libere a leitura para a service account do Cloud Run:

```bash
for SECRET in mnemio-tmdb-token mnemio-google-books-key; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member=serviceAccount:mnemio-api@mnemio-prod-f25c.iam.gserviceaccount.com \
    --role=roles/secretmanager.secretAccessor
done
```

## 2.3 Primeiro deploy com as chaves

```bash
cd backend

gcloud run deploy mnemio-api \
  --source . \
  --region southamerica-east1 \
  --project mnemio-prod-f25c \
  --update-secrets TMDB_API_READ_ACCESS_TOKEN=mnemio-tmdb-token:latest,GOOGLE_BOOKS_API_KEY=mnemio-google-books-key:latest
```

`--update-secrets` **acrescenta** os dois e preserva `SECRET_KEY` e `DATABASE_URL`.
Não use `--set-secrets`: esse substitui a lista inteira e derruba os que já existem.

## 2.4 As migrations

Não precisa rodar nada à mão: `entrypoint.sh` executa `alembic upgrade head` antes de subir
o uvicorn. Se falhar, o container morre, o Cloud Run mantém a revisão antiga servindo e o
deploy é revertido — falha barulhenta, de propósito.

Estado do Neon quando esta doc foi escrita:

| Item | Estado |
|---|---|
| Versão aplicada | `b2f4a9c17d30` |
| A aplicar | `c1a7d5e9b430` → `d2b8e6f1c547` → `e3c9f7a2d658` |
| `pg_trgm` | disponível, e `neondb_owner` tem permissão de criar (testado em transação revertida) |
| Risco | nenhum: as três migrations só adicionam tabelas e colunas |

Se preferir aplicar antes, para ver o resultado com calma:

```bash
DATABASE_URL='<url do Neon>' ./venv/bin/alembic upgrade head
DATABASE_URL='<url do Neon>' ./venv/bin/alembic current   # deve mostrar e3c9f7a2d658 (head)
```

---

# Parte 3 — Deploy no dia a dia

## 3.1 Subir a API

```bash
cd backend
gcloud run deploy mnemio-api --source . --region southamerica-east1
```

Só isso. Os segredos já estão configurados no serviço e as migrations rodam no boot.

Antes de subir, rode a suíte:

```bash
./venv/bin/pytest -q     # 162 testes, sem tocar em rede
```

## 3.2 Conferir que subiu

```bash
API=https://mnemio-api-cj354xkp5a-rj.a.run.app

curl -s $API/

TOKEN=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"SEU@EMAIL","password":"SUA_SENHA"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s -H "Authorization: Bearer $TOKEN" "$API/busca?q=duna&tipo=filmes"      | head -c 300
curl -s -H "Authorization: Bearer $TOKEN" "$API/busca?q=mistborn&tipo=livros"  | head -c 300
curl -s -H "Authorization: Bearer $TOKEN" "$API/busca?q=round%206&tipo=doramas" | head -c 300
```

## 3.3 Quando algo dá errado

| Sintoma | Causa provável |
|---|---|
| Busca volta `[]` com header `X-Search-Degraded: true` | chave da fonte ausente, errada, ou com `\n` no fim (use `printf`, não `echo`) |
| Só livros degradado | quota diária do Google Books estourada |
| Todas as buscas degradadas | segredos não chegaram no container: `gcloud run services describe mnemio-api --region southamerica-east1` |
| Container não sobe | `alembic upgrade head` falhou |
| `503 not available yet` | faturamento (Parte 1) |

Os logs dizem o motivo exato de cada degradação:

```bash
gcloud run services logs read mnemio-api --region southamerica-east1 --limit 50
```

## 3.4 Rollback

```bash
gcloud run revisions list --service mnemio-api --region southamerica-east1

gcloud run services update-traffic mnemio-api \
  --region southamerica-east1 --to-revisions REVISAO_ANTIGA=100
```

O schema é aditivo, então a revisão antiga funciona normalmente com o banco já migrado —
ela simplesmente ignora as tabelas e colunas novas. `alembic downgrade` só se for mesmo
necessário desfazer o schema.

## 3.5 Subir o app

`eas.json` já aponta para o Cloud Run nos perfis `preview` e `production`.

```bash
cd frontend
npx eas build --profile preview --platform android      # APK de teste
npx eas build --profile production --platform android
npx eas submit --profile production --platform android
```

---

# Ambiente local

```bash
cd backend
docker compose up -d                      # Postgres local na porta 5433
./venv/bin/alembic upgrade head
./venv/bin/uvicorn app.main:app --host 0.0.0.0 --reload
```

`backend/.env` precisa de:

```bash
SECRET_KEY=<gere com: python3 -c "import secrets; print(secrets.token_hex(32))">
DATABASE_URL=postgresql+psycopg://mnemio:mnemio@localhost:5433/mnemio
TMDB_API_READ_ACCESS_TOKEN=<token v4>
GOOGLE_BOOKS_API_KEY=<chave>
```

> **Cuidado:** deixe o `DATABASE_URL` local apontando para o Postgres do docker-compose.
> Com a URL do Neon aí, qualquer `alembic upgrade` ou script roda contra os dados reais de
> produção. A URL de produção deve viver só no Secret Manager.

Sem as chaves de API o backend sobe igual: a busca do tipo correspondente degrada e avisa no
log, em vez de quebrar.
