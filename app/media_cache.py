"""Cache sob demanda do catálogo de mídias.

Nada de catálogo é importado em massa: um item só entra em media_items quando
o usuário interage com ele (abre o detalhe, ou avalia/adiciona à lista).

Concorrência é resolvida no banco, pelo índice único (source, external_id):
o upsert é um único statement `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`.
Checar com SELECT antes de inserir teria race condition — entre o SELECT e o
INSERT cabe outra transação.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import config, media_sources, models
from app.database import SessionLocal
from app.media_sources.base import MediaSourceError, NormalizedMedia

logger = logging.getLogger(__name__)

# Fábrica de sessões usada pelas tarefas de background. A sessão do request
# (get_db) fecha junto com a resposta, então o background precisa da sua.
# Os testes trocam isto pela sessão SQLite em memória.
SESSION_FACTORY = SessionLocal

# Quantos vínculos pendentes uma varredura oportunista tenta por vez.
SWEEP_BATCH = 5
MAX_ATTEMPTS = 5

# Modelo de item do usuário por tipo de rota, para religar um vínculo pendente.
USER_MEDIA_MODELS = {
    "livros": models.Livro,
    "series": models.Serie,
    "filmes": models.Filme,
    "animes": models.Anime,
    "doramas": models.Dorama,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Colunas DateTime voltam sem tzinfo; assume UTC, que é o que foi gravado."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Leitura do cache
# --------------------------------------------------------------------------


def get_cached(db: Session, source: str, external_id: str) -> models.MediaItem | None:
    return (
        db.query(models.MediaItem)
        .filter(
            models.MediaItem.source == source,
            models.MediaItem.external_id == str(external_id),
        )
        .first()
    )


def is_stale(item: models.MediaItem) -> bool:
    """Vencido pelo TTL. Item vencido ainda é servido — o refresh é em background."""
    ttl = timedelta(days=config.cache_ttl_days())
    return _as_utc(item.refreshed_at) + ttl < _now()


def cached_ids(db: Session, results: list[NormalizedMedia]) -> dict[tuple[str, str], int]:
    """Quais resultados da busca já estão no cache, em um único SELECT."""
    if not results:
        return {}

    pairs = {(item.source, item.external_id) for item in results}
    rows = db.execute(
        select(models.MediaItem.id, models.MediaItem.source, models.MediaItem.external_id).where(
            models.MediaItem.source.in_({source for source, _ in pairs}),
            models.MediaItem.external_id.in_({external for _, external in pairs}),
        )
    ).all()

    return {(source, external): media_id for media_id, source, external in rows if (source, external) in pairs}


def local_search(db: Session, media_type: str, query: str, limit: int) -> list[models.MediaItem]:
    """Fallback quando a fonte externa está fora: devolve o que já foi cacheado.

    Usa o índice trigram de media_items.title.
    """
    pattern = f"%{query.strip()}%"
    return (
        db.query(models.MediaItem)
        .filter(models.MediaItem.media_type == media_type, models.MediaItem.title.ilike(pattern))
        .order_by(models.MediaItem.title)
        .limit(limit)
        .all()
    )


# --------------------------------------------------------------------------
# Escrita: upsert idempotente
# --------------------------------------------------------------------------


def _insert_stmt(db: Session):
    """`ON CONFLICT` é específico do dialeto.

    Produção é Postgres; a suíte roda em SQLite em memória. Os dois suportam
    a mesma semântica, só não compartilham o construtor.
    """
    if db.get_bind().dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert


def upsert_media_item(db: Session, media: NormalizedMedia) -> int:
    """Grava (ou atualiza) o item de catálogo e devolve o id.

    Idempotente: dois usuários adicionando o mesmo item ao mesmo tempo geram
    uma linha só. O segundo INSERT colide no índice único, cai no DO UPDATE e
    o RETURNING devolve o id da linha existente.

    Não faz commit: quem chama decide quando persistir.
    """
    insert = _insert_stmt(db)
    now = _now()
    values = media.as_dict()

    stmt = (
        insert(models.MediaItem)
        .values(**values, refreshed_at=now, created_at=now, updated_at=now)
        .on_conflict_do_update(
            index_elements=["source", "external_id"],
            set_={
                "media_type": values["media_type"],
                "title": values["title"],
                "original_title": values["original_title"],
                "poster_url": values["poster_url"],
                "release_year": values["release_year"],
                "synopsis": values["synopsis"],
                "raw_payload": values["raw_payload"],
                "refreshed_at": now,
                "updated_at": now,
            },
        )
        .returning(models.MediaItem.id)
    )

    return db.execute(stmt).scalar_one()


# --------------------------------------------------------------------------
# Vínculos pendentes (outbox)
#
# Falhar ao gravar o catálogo não pode virar erro visível: a avaliação do
# usuário é gravada com media_id nulo e o vínculo é refeito depois.
# --------------------------------------------------------------------------


def enqueue_pending_link(
    db: Session, *, user_id: int, route_type: str, item_id: int, source: str, external_id: str
) -> None:
    existing = (
        db.query(models.PendingMediaLink)
        .filter(
            models.PendingMediaLink.route_type == route_type,
            models.PendingMediaLink.item_id == item_id,
        )
        .first()
    )
    if existing:
        existing.source = source
        existing.external_id = external_id
        return

    db.add(
        models.PendingMediaLink(
            user_id=user_id,
            route_type=route_type,
            item_id=item_id,
            source=source,
            external_id=external_id,
        )
    )


def _link_item(db: Session, route_type: str, item_id: int, media_id: int) -> None:
    model = USER_MEDIA_MODELS.get(route_type)
    if model is None:
        return
    item = db.query(model).filter(model.id == item_id).first()
    if item is not None:
        item.media_id = media_id


def _due(link: models.PendingMediaLink, now: datetime) -> bool:
    """Backoff exponencial: 1, 2, 4, 8... minutos entre tentativas."""
    if link.attempts >= MAX_ATTEMPTS:
        return False
    if link.last_attempt_at is None:
        return True
    delay = timedelta(minutes=2 ** min(link.attempts, 6))
    return _as_utc(link.last_attempt_at) + delay <= now


# --------------------------------------------------------------------------
# Tarefas de background
#
# São async porque a chamada HTTP é async; a parte de banco (SQLAlchemy sync)
# roda em threadpool para não travar o event loop.
# Nenhuma delas levanta: são best-effort por definição.
# --------------------------------------------------------------------------


def _persist(media: NormalizedMedia) -> int | None:
    db = SESSION_FACTORY()
    try:
        media_id = upsert_media_item(db, media)
        db.commit()
        return media_id
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("Falha ao gravar %s/%s no cache", media.source, media.external_id, exc_info=True)
        return None
    finally:
        db.close()


async def persist_media_item(route_type: str, source: str, external_id: str) -> None:
    """Busca o detalhe na fonte e grava no cache. Chamada depois da resposta ir para o app."""
    try:
        media = await media_sources.fetch(route_type, source, external_id)
    except MediaSourceError as exc:
        logger.warning("Não foi possível buscar %s/%s: %s", source, external_id, exc)
        return

    if media is None:
        return

    await run_in_threadpool(_persist, media)


async def persist_normalized(media: NormalizedMedia) -> None:
    """Grava um item que já veio normalizado (a resposta do detalhe, por exemplo)."""
    await run_in_threadpool(_persist, media)


def _resolve_link_sync(link_id: int, media: NormalizedMedia | None, error: str | None) -> None:
    db = SESSION_FACTORY()
    try:
        link = db.query(models.PendingMediaLink).filter(models.PendingMediaLink.id == link_id).first()
        if link is None:
            return

        if media is None:
            link.attempts += 1
            link.last_attempt_at = _now()
            link.last_error = (error or "sem resultado")[:500]
            db.commit()
            return

        media_id = upsert_media_item(db, media)
        _link_item(db, link.route_type, link.item_id, media_id)
        db.delete(link)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.warning("Falha ao resolver vínculo pendente %s", link_id, exc_info=True)
    finally:
        db.close()


def _pending_batch(user_id: int | None) -> list[tuple[int, str, str, str]]:
    db = SESSION_FACTORY()  # noqa: F821 - trocado pelos testes
    try:
        query = db.query(models.PendingMediaLink).filter(
            models.PendingMediaLink.attempts < MAX_ATTEMPTS
        )
        if user_id is not None:
            query = query.filter(models.PendingMediaLink.user_id == user_id)

        now = _now()
        links = query.order_by(models.PendingMediaLink.created_at).limit(SWEEP_BATCH * 4).all()
        return [
            (link.id, link.route_type, link.source, link.external_id)
            for link in links
            if _due(link, now)
        ][:SWEEP_BATCH]
    finally:
        db.close()


async def sweep_pending_links(user_id: int | None = None) -> None:
    """Reprocessa vínculos pendentes.

    Disparada de forma oportunista na próxima request do mesmo usuário — sem
    broker, sem worker. No uso normal isso resolve em minutos.
    """
    try:
        batch = await run_in_threadpool(_pending_batch, user_id)
    except Exception:  # noqa: BLE001 - background nunca derruba nada
        logger.warning("Não foi possível ler os vínculos pendentes", exc_info=True)
        return

    for link_id, route_type, source, external_id in batch:
        media: NormalizedMedia | None = None
        error: str | None = None
        try:
            media = await media_sources.fetch(route_type, source, external_id)
        except MediaSourceError as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            logger.exception("Erro inesperado no vínculo pendente %s", link_id)

        await run_in_threadpool(_resolve_link_sync, link_id, media, error)
