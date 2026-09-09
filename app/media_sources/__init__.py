"""Runtime das fontes externas: client HTTP compartilhado, cache de busca e circuit breaker.

Regra que vale para tudo aqui: falha de fonte externa nunca vira 5xx. A busca
degrada para o cache local (app/media_cache.py) e o app segue funcionando.
"""

import logging
import time
from collections import OrderedDict

import httpx

from app import config
from app.media_sources import anilist, google_books, tmdb  # noqa: F401 - anilist está parado, ver CLIENTS
from app.media_sources.base import (
    MediaSourceClient,
    MediaSourceError,
    MediaSourceUnconfigured,
    NormalizedMedia,
)

logger = logging.getLogger(__name__)

# Um client por tipo de mídia, na chave plural usada pelas rotas e pelo app.
#
# Anime está fora: a AniList desativou a API pública ("The AniList API has been
# temporarily disabled due to severe stability issues", 403). O client continua
# em app/media_sources/anilist.py, testado — basta reinserir a linha abaixo
# quando a API voltar:
#     "animes": anilist.CLIENT,
# Enquanto isso, anime segue com cadastro manual pelo CRUD /animes.
CLIENTS: dict[str, MediaSourceClient] = {
    "filmes": tmdb.MOVIE_CLIENT,
    "series": tmdb.SERIE_CLIENT,
    "doramas": tmdb.DORAMA_CLIENT,
    "livros": google_books.CLIENT,
}

# --------------------------------------------------------------------------
# Client HTTP compartilhado
#
# Um AsyncClient por processo, criado no lifespan do app. Criar um por request
# joga fora o pool de conexões e o handshake TLS — é a diferença entre ~40ms e
# ~250ms por busca.
# --------------------------------------------------------------------------

_http: httpx.AsyncClient | None = None


def startup() -> None:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            follow_redirects=True,
            headers={"User-Agent": "Mnemio/1.0 (+https://github.com/mnemio)"},
        )


async def shutdown() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None
    _search_cache.clear()
    _breakers.clear()


def _client() -> httpx.AsyncClient:
    """O lifespan cria o client; este fallback cobre teste e script avulso."""
    if _http is None:
        startup()
    return _http


# --------------------------------------------------------------------------
# Circuit breaker por fonte
#
# Sem ele, 20 requests ficam presas em timeout de 2,5s cada quando a fonte cai.
# --------------------------------------------------------------------------

FAILURE_THRESHOLD = 5
OPEN_SECONDS = 30.0

_breakers: dict[str, dict] = {}


def _breaker(key: str) -> dict:
    return _breakers.setdefault(key, {"failures": 0, "open_until": 0.0})


def _is_open(key: str) -> bool:
    return _breaker(key)["open_until"] > time.monotonic()


def _record_failure(key: str) -> None:
    state = _breaker(key)
    state["failures"] += 1
    if state["failures"] >= FAILURE_THRESHOLD:
        state["open_until"] = time.monotonic() + OPEN_SECONDS
        state["failures"] = 0
        logger.warning("Circuit breaker aberto para %s por %.0fs", key, OPEN_SECONDS)


def _record_success(key: str) -> None:
    _breakers[key] = {"failures": 0, "open_until": 0.0}


# --------------------------------------------------------------------------
# Cache de busca (in-process, LRU + TTL)
#
# Mata o custo do autocomplete repetido ("f", "fr", "fri", apagou, digitou de
# novo) e ajuda no rate limit. É por processo do uvicorn: some no reload e não
# é compartilhado entre workers. Para o volume atual, suficiente.
# --------------------------------------------------------------------------

SEARCH_CACHE_MAXSIZE = 512

_search_cache: OrderedDict[tuple, tuple[float, list[NormalizedMedia]]] = OrderedDict()


def _cache_key(route_type: str, query: str, limit: int) -> tuple:
    return (route_type, query.strip().casefold(), limit)


def _cache_get(key: tuple) -> list[NormalizedMedia] | None:
    entry = _search_cache.get(key)
    if entry is None:
        return None
    expires_at, results = entry
    if expires_at < time.monotonic():
        _search_cache.pop(key, None)
        return None
    _search_cache.move_to_end(key)
    return results


def _cache_put(key: tuple, results: list[NormalizedMedia]) -> None:
    _search_cache[key] = (time.monotonic() + config.search_cache_ttl_seconds(), results)
    _search_cache.move_to_end(key)
    while len(_search_cache) > SEARCH_CACHE_MAXSIZE:
        _search_cache.popitem(last=False)


# --------------------------------------------------------------------------
# API do módulo
# --------------------------------------------------------------------------


def supports(route_type: str) -> bool:
    return route_type in CLIENTS


async def search(route_type: str, query: str, *, limit: int = 20) -> tuple[list[NormalizedMedia], bool]:
    """Busca na fonte externa.

    Devolve (resultados, degradado). `degradado=True` significa que a fonte não
    respondeu e quem chama deve cair no cache local — nunca levanta por falha
    de rede, timeout ou rate limit.
    """
    client = CLIENTS.get(route_type)
    if client is None:
        return [], False

    key = _cache_key(route_type, query, limit)
    cached = _cache_get(key)
    if cached is not None:
        return cached, False

    if _is_open(route_type):
        logger.info("Busca em %s pulada: circuit breaker aberto", route_type)
        return [], True

    try:
        results = await client.search(_client(), query, limit=limit)
    except MediaSourceUnconfigured as exc:
        # Sem chave de API: degrada, mas não conta como falha da fonte.
        logger.warning("Fonte %s não configurada: %s", route_type, exc)
        return [], True
    except MediaSourceError as exc:
        _record_failure(route_type)
        logger.warning("Busca em %s falhou: %s", route_type, exc)
        return [], True
    except Exception as exc:  # noqa: BLE001 - fonte externa não derruba a busca
        _record_failure(route_type)
        logger.exception("Erro inesperado buscando em %s: %s", route_type, exc)
        return [], True

    _record_success(route_type)
    _cache_put(key, results)
    return results, False


async def fetch(route_type: str, source: str, external_id: str) -> NormalizedMedia | None:
    """Detalhe de um item na fonte. Levanta MediaSourceError se a fonte falhar.

    Diferente da busca, aqui quem chama decide o que fazer: o router devolve o
    que tem em cache, e a tarefa de background só desiste e tenta de novo depois.
    """
    client = CLIENTS.get(route_type)
    if client is None or client.source != source:
        return None
    if _is_open(route_type):
        raise MediaSourceError(f"Circuit breaker aberto para {route_type}")

    try:
        result = await client.fetch(_client(), external_id)
    except MediaSourceError:
        _record_failure(route_type)
        raise
    except Exception as exc:  # noqa: BLE001
        _record_failure(route_type)
        raise MediaSourceError(str(exc)) from exc

    _record_success(route_type)
    return result
