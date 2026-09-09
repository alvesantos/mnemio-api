"""TMDB — filmes, séries e doramas.

Dorama não é uma fonte separada: é o mesmo /search/tv, filtrado por
origin_country. Por isso a aba de séries precisa excluir o que a de doramas
inclui, senão "Round 6" aparece nas duas.
"""

import httpx

from app import config
from app.media_sources.base import (
    MediaSourceError,
    MediaSourceUnconfigured,
    NormalizedMedia,
    clean_text,
    parse_year,
    strip_html,
    truncate,
)
from app.models import MediaSource, MediaType

BASE_URL = "https://api.themoviedb.org/3"
# w342 é o melhor equilíbrio para lista mobile; a tela de detalhe reusa a mesma.
IMAGE_BASE = "https://image.tmdb.org/t/p/w342"
LANGUAGE = "pt-BR"
FALLBACK_LANGUAGE = "en-US"

TITLE_LIMIT = 300
URL_LIMIT = 500

# Quantas páginas buscar no máximo quando o filtro de dorama derruba a maioria
# dos resultados de uma página.
MAX_PAGES = 2


def _headers() -> dict[str, str]:
    token = config.tmdb_token()
    if not token:
        raise MediaSourceUnconfigured("TMDB_API_READ_ACCESS_TOKEN não configurado")
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


async def _get(http: httpx.AsyncClient, path: str, params: dict, timeout: float) -> dict:
    try:
        response = await http.get(
            f"{BASE_URL}{path}", params=params, headers=_headers(), timeout=timeout
        )
    except httpx.HTTPError as exc:
        raise MediaSourceError(f"TMDB indisponível: {exc}") from exc

    if response.status_code == 404:
        return {}
    if response.status_code != 200:
        # 429 vem com Retry-After; para a busca é só mais uma falha degradável.
        raise MediaSourceError(f"TMDB respondeu {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise MediaSourceError("TMDB devolveu JSON inválido") from exc


def _poster_url(poster_path: str | None) -> str | None:
    if not poster_path:
        return None
    return truncate(f"{IMAGE_BASE}{poster_path}", URL_LIMIT)


def _original(title: str, original_title: str | None) -> str | None:
    """Só guarda o título original quando ele acrescenta informação."""
    original = clean_text(original_title)
    if not original or original == title:
        return None
    return truncate(original, TITLE_LIMIT)


class TmdbMovieClient:
    source = MediaSource.TMDB
    media_type = MediaType.FILME

    def normalize(self, raw: dict) -> NormalizedMedia:
        title = truncate(
            clean_text(raw.get("title")) or clean_text(raw.get("original_title")) or "Sem título",
            TITLE_LIMIT,
        )
        return NormalizedMedia(
            source=self.source,
            external_id=str(raw["id"]),
            media_type=self.media_type,
            title=title,
            original_title=_original(title, raw.get("original_title")),
            poster_url=_poster_url(raw.get("poster_path")),
            release_year=parse_year(raw.get("release_date")),
            synopsis=strip_html(clean_text(raw.get("overview"))),
            raw_payload=raw,
        )

    async def search(
        self, http: httpx.AsyncClient, query: str, *, limit: int
    ) -> list[NormalizedMedia]:
        data = await _get(
            http,
            "/search/movie",
            {"query": query, "language": LANGUAGE, "include_adult": "false", "page": 1},
            config.search_timeout(),
        )
        results = data.get("results") or []
        return [self.normalize(raw) for raw in results[:limit]]

    async def fetch(self, http: httpx.AsyncClient, external_id: str) -> NormalizedMedia | None:
        data = await _get(
            http, f"/movie/{external_id}", {"language": LANGUAGE}, config.fetch_timeout()
        )
        if not data:
            return None

        # pt-BR devolve overview vazio para muito título de nicho; só aí paga
        # uma segunda chamada em inglês.
        if not clean_text(data.get("overview")):
            fallback = await _get(
                http,
                f"/movie/{external_id}",
                {"language": FALLBACK_LANGUAGE},
                config.fetch_timeout(),
            )
            if clean_text(fallback.get("overview")):
                data["overview"] = fallback["overview"]

        return self.normalize(data)


class TmdbTvClient:
    """Séries e doramas. `dorama=True` inverte o filtro de país de origem."""

    source = MediaSource.TMDB

    def __init__(self, *, dorama: bool) -> None:
        self.dorama = dorama
        self.media_type = MediaType.DORAMA if dorama else MediaType.SERIE

    def _is_dorama(self, raw: dict) -> bool:
        countries = {str(code).upper() for code in (raw.get("origin_country") or [])}
        return bool(countries & config.dorama_origin_countries())

    def matches(self, raw: dict) -> bool:
        return self._is_dorama(raw) == self.dorama

    def normalize(self, raw: dict) -> NormalizedMedia:
        title = truncate(
            clean_text(raw.get("name")) or clean_text(raw.get("original_name")) or "Sem título",
            TITLE_LIMIT,
        )
        # Classifica pelo país de origem do próprio item, e não pelo client que
        # atendeu: assim abrir /midias/series/tmdb/<id> de uma série coreana
        # ainda grava media_type="dorama".
        return NormalizedMedia(
            source=self.source,
            external_id=str(raw["id"]),
            media_type=MediaType.DORAMA if self._is_dorama(raw) else MediaType.SERIE,
            title=title,
            original_title=_original(title, raw.get("original_name")),
            poster_url=_poster_url(raw.get("poster_path")),
            release_year=parse_year(raw.get("first_air_date")),
            synopsis=strip_html(clean_text(raw.get("overview"))),
            raw_payload=raw,
        )

    async def search(
        self, http: httpx.AsyncClient, query: str, *, limit: int
    ) -> list[NormalizedMedia]:
        collected: list[NormalizedMedia] = []
        page = 1
        total_pages = 1

        # Uma página de 20 resultados pode virar 3 doramas depois do filtro;
        # daí buscar a segunda enquanto faltar item e houver página.
        while page <= min(MAX_PAGES, total_pages) and len(collected) < limit:
            data = await _get(
                http,
                "/search/tv",
                {"query": query, "language": LANGUAGE, "page": page},
                config.search_timeout(),
            )
            total_pages = data.get("total_pages") or 1
            for raw in data.get("results") or []:
                if self.matches(raw):
                    collected.append(self.normalize(raw))
                    if len(collected) == limit:
                        break
            page += 1

        return collected

    async def fetch(self, http: httpx.AsyncClient, external_id: str) -> NormalizedMedia | None:
        data = await _get(
            http, f"/tv/{external_id}", {"language": LANGUAGE}, config.fetch_timeout()
        )
        if not data:
            return None

        if not clean_text(data.get("overview")):
            fallback = await _get(
                http,
                f"/tv/{external_id}",
                {"language": FALLBACK_LANGUAGE},
                config.fetch_timeout(),
            )
            if clean_text(fallback.get("overview")):
                data["overview"] = fallback["overview"]

        return self.normalize(data)


MOVIE_CLIENT = TmdbMovieClient()
SERIE_CLIENT = TmdbTvClient(dorama=False)
DORAMA_CLIENT = TmdbTvClient(dorama=True)
