# Busca de mídias e cache sob demanda

Como o catálogo de mídias funciona. Substitui a spec de proposta — este documento descreve o
que está implementado.

## O problema

O app não tinha catálogo: o usuário digitava o título na mão. Importar os catálogos das APIs
externas seria dezenas de GB de dados que quase ninguém consulta.

A saída é cache sob demanda: a busca vai sempre na fonte externa, em tempo real, e o banco
guarda só os itens com os quais o usuário realmente interagiu.

## Fluxo

```
usuário digita
   -> GET /busca (fonte externa em tempo real)     ... NADA é gravado
   -> toca num resultado
      -> GET /midias/{tipo}/{source}/{external_id}
         cache HIT fresco   -> serve do banco
         cache HIT vencido  -> serve do banco AGORA + atualiza em background
         cache MISS         -> busca na fonte, responde, e grava em background
   -> avalia / adiciona à lista
      -> POST /filmes (com media_ref)
         cache HIT   -> vincula na hora
         cache MISS  -> grava a avaliação sem vínculo e manda o vínculo pra outbox
```

A gravação nunca está no caminho crítico da resposta. O usuário não paga o custo de "salvar
no banco na primeira vez".

## Fontes

| Tipo | Fonte | Autenticação |
|---|---|---|
| Filmes | TMDB `/search/movie` | token v4 (Bearer) |
| Séries | TMDB `/search/tv` | token v4 |
| Doramas | TMDB `/search/tv` filtrado por `origin_country` | token v4 |
| Livros | Google Books `/volumes` | chave de API |
| Animes | — | fora: a AniList desativou a API pública |

Dorama não é uma fonte separada: é o mesmo endpoint de séries, filtrado por país de origem
(`DORAMA_ORIGIN_COUNTRIES`, hoje `KR`). A aba de séries exclui o que a de doramas inclui,
senão "Round 6" apareceria nas duas. A classificação sai do próprio item, não da rota que
atendeu — abrir uma série coreana pela rota de séries ainda grava `dorama`.

Anime continua com cadastro manual: o CRUD `/animes` e os dados existentes não foram
tocados. O client da AniList está pronto em `app/media_sources/anilist.py`; religar é
devolver a linha `"animes": anilist.CLIENT` ao dicionário `CLIENTS` de
`app/media_sources/__init__.py`.

## Modelo de dados

`media_items` é catálogo **global**, sem `user_id` — o mesmo filme serve todos os usuários.
As tabelas por tipo (`livros`, `series`, `filmes`, `animes`, `doramas`) continuam sendo a
avaliação de cada um e apontam para o catálogo por `media_id`, que é **nullable**: o cadastro
manual continua existindo e os itens antigos não têm vínculo.

O índice único `(source, external_id)` é o mecanismo de deduplicação. `external_id` é
`String` porque o Google Books usa id alfanumérico enquanto TMDB e AniList usam inteiro.

## Concorrência

Dois usuários adicionando o mesmo item ao mesmo tempo resolvem em um único statement:

```sql
INSERT INTO media_items (...) VALUES (...)
ON CONFLICT (source, external_id) DO UPDATE SET ...
RETURNING id
```

O segundo INSERT colide no índice único, cai no `DO UPDATE` e o `RETURNING` devolve o id da
linha existente. Uma linha, zero erro, zero retry.

Verificar com `SELECT` antes de inserir teria race condition: entre o SELECT e o INSERT cabe
outra transação.

`ON CONFLICT` é específico do dialeto — produção é Postgres, a suíte roda em SQLite —, daí o
branch em `media_cache._insert_stmt`.

## Cache

TTL de 30 dias (`MEDIA_CACHE_TTL_DAYS`) com stale-while-revalidate: item vencido é servido do
banco na hora e atualizado depois, em background.

Há ainda um cache de busca em memória, de 60 segundos, que mata o custo do autocomplete
repetido. É por processo do uvicorn: some no reload e não é compartilhado entre workers.

## Quando a fonte cai

Nunca vira 5xx. A ordem de degradação da busca é:

1. Timeout, 5xx ou 429 na fonte → log em WARNING
2. Fallback local: `title ILIKE %q%` em `media_items`, usando o índice trigram
3. Resposta 200 com header `X-Search-Degraded: true` — o app mostra um aviso discreto
4. Lista vazia é estado normal da UI, não erro

Depois de 5 falhas seguidas, um circuit breaker pula a fonte por 30 segundos, para não
acumular 20 requests presas em timeout.

## Falha ao gravar não vira erro

Três camadas:

1. **Detalhe** — gravação em background; falhar não muda nada na tela. Tenta de novo no
   próximo acesso.
2. **Avaliação** — o item do usuário é gravado **sempre**, com `media_id` nulo se o catálogo
   falhar. A nota é o dado importante; o metadado é recuperável.
3. **Outbox** — `pending_media_links` guarda o vínculo pendente, com backoff exponencial e
   limite de 5 tentativas. A varredura é oportunista: roda em background na próxima request
   do mesmo usuário. Sem broker, sem worker.

## Timeouts e limites das fontes

| Chamada | Timeout | Por quê |
|---|---|---|
| Busca | 2,5s | acima disso o usuário já desistiu |
| Detalhe | 3,0s | tem tela de loading legítima |
| Background | 5,0s | ninguém está esperando |

Sem retry na busca: o usuário digita de novo, e retry em cima de timeout multiplica carga na
hora errada. Retry só em background.

| Fonte | Limite | Observação |
|---|---|---|
| TMDB | ~50 req/s por IP | folgado para o volume do app |
| Google Books | 1.000 req/dia por projeto | o gargalo real; debounce e cache não são opcionais |
| AniList | 30–90 req/min | irrelevante enquanto a API estiver desativada |

## Fora de escopo

Sincronização periódica de dados vencidos, importação em massa, fontes além das listadas,
busca multi-tipo numa chamada, deduplicação entre edições do mesmo livro, e hospedar imagens
(só a URL é guardada, nunca o binário).

## Decisões ainda em aberto

- Um usuário pode adicionar o mesmo item duas vezes (releitura, rewatch)? Se não, entra um
  índice único parcial `(user_id, media_id)`.
- Migrar a suíte de testes para o Postgres do docker-compose: só assim o teste de
  concorrência do upsert entra na suíte, em vez de ficar como verificação manual.
- Item despublicado na fonte (404 no refresh): manter em cache, ou marcar como indisponível?
- Esperar a AniList voltar ou adotar uma fonte alternativa (Jikan/MyAnimeList) para animes?
