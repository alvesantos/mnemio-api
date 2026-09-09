"""Busca em tempo real nas fontes externas e leitura do catálogo cacheado.

A busca nunca persiste nada: é o que impede o banco encher de item que ninguém
consumiu. A gravação acontece quando o usuário abre o detalhe (em background)
ou avalia (ver app/crud_router.py).
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app import media_cache, media_sources, models, schemas
from app.database import get_db
from app.deps import get_current_user
from app.media_sources.base import MediaSourceError, NormalizedMedia

logger = logging.getLogger(__name__)

router = APIRouter(tags=["catalogo"])

# Abaixo disso a busca não vale a chamada externa. Devolve lista vazia em vez
# de 422: o app dispara a cada pausa da digitação, um erro seria hostil.
MIN_QUERY_LENGTH = 2

# Sinaliza para o app que o resultado veio só do cache local porque a fonte
# não respondeu. A UI mostra um aviso discreto, nunca um alerta de erro.
DEGRADED_HEADER = "X-Search-Degraded"

SEM_FONTE = "Busca externa indisponível para este tipo. Cadastre manualmente."


def _require_source(tipo: str) -> None:
    """Tipo sem fonte configurada (hoje: animes) responde claro, não vazio.

    Devolver lista vazia esconderia o motivo e o app não teria como mandar o
    usuário para o cadastro manual.
    """
    if not media_sources.supports(tipo):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=SEM_FONTE)


def _from_normalized(media: NormalizedMedia, *, media_id: int | None) -> dict:
    return {
        "source": media.source,
        "external_id": media.external_id,
        "media_type": media.media_type,
        "title": media.title,
        "original_title": media.original_title,
        "poster_url": media.poster_url,
        "release_year": media.release_year,
        "synopsis": media.synopsis,
        "cached": media_id is not None,
        "media_id": media_id,
    }


def _from_row(row: models.MediaItem) -> dict:
    return {
        "source": row.source,
        "external_id": row.external_id,
        "media_type": row.media_type,
        "title": row.title,
        "original_title": row.original_title,
        "poster_url": row.poster_url,
        "release_year": row.release_year,
        "synopsis": row.synopsis,
        "cached": True,
        "media_id": row.id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "refreshed_at": row.refreshed_at,
    }


@router.get("/busca", response_model=list[schemas.MediaSearchResult])
async def buscar(
    response: Response,
    tipo: schemas.MediaTypeLiteral,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=40),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Busca direto na fonte externa, em tempo real.

    Vai sempre na fonte (respeitando o cache de curta duração) para o resultado
    nunca sair incompleto — o banco guarda só o que o usuário já tocou.
    """
    _require_source(tipo)

    query = q.strip()
    if len(query) < MIN_QUERY_LENGTH:
        return []

    results, degraded = await media_sources.search(tipo, query, limit=limit)

    if degraded:
        response.headers[DEGRADED_HEADER] = "true"

    if not results:
        if not degraded:
            return []
        # Fonte fora do ar: devolve o que já está cacheado em vez de erro.
        media_type = models.ROUTE_TO_MEDIA_TYPE[tipo]
        rows = await run_in_threadpool(media_cache.local_search, db, media_type, query, limit)
        return [_from_row(row) for row in rows]

    index = await run_in_threadpool(media_cache.cached_ids, db, results)
    return [
        _from_normalized(media, media_id=index.get((media.source, media.external_id)))
        for media in results
    ]


@router.get("/midias/{tipo}/{source}/{external_id}", response_model=schemas.MediaItemOut)
async def detalhe(
    tipo: schemas.MediaTypeLiteral,
    source: schemas.MediaSourceLiteral,
    external_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Detalhe de um item de catálogo.

    HIT e fresco: devolve do banco.
    HIT e vencido: devolve do banco agora e atualiza em background (o usuário
    nunca espera um refresh).
    MISS: busca na fonte, devolve, e grava em background.
    """
    cached = await run_in_threadpool(media_cache.get_cached, db, source, external_id)

    if cached is None:
        # Item fora do cache só pode vir da fonte; sem fonte, não há o que servir.
        _require_source(tipo)

    if cached is not None:
        if media_cache.is_stale(cached):
            background_tasks.add_task(
                media_cache.persist_media_item, tipo, source, external_id
            )
        return _from_row(cached)

    try:
        media = await media_sources.fetch(tipo, source, external_id)
    except MediaSourceError as exc:
        logger.warning("Detalhe de %s/%s indisponível: %s", source, external_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fonte externa indisponível no momento.",
        )

    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    # Primeira interação real com o item: agora vale guardar. Depois da resposta,
    # para o usuário não pagar o custo da gravação.
    background_tasks.add_task(media_cache.persist_normalized, media)

    return _from_normalized(media, media_id=None)
