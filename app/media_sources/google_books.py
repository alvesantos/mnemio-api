"""Google Books — livros.

Cada edição é um item distinto (IDs diferentes para o mesmo livro): é o
comportamento honesto, o usuário escolhe a edição que leu. Deduplicar por
ISBN/obra está fora de escopo.

A quota do free tier (1.000 req/dia por projeto) é o primeiro gargalo do
sistema, então debounce no app e cache de busca não são opcionais aqui.
"""

import httpx

from app import config
from app.media_sources.base import (
    MediaSourceError,
    NormalizedMedia,
    clean_text,
    parse_year,
    strip_html,
    truncate,
)
from app.models import MediaSource, MediaType

BASE_URL = "https://www.googleapis.com/books/v1"

TITLE_LIMIT = 300
URL_LIMIT = 500


def _params(extra: dict) -> dict:
    params = {"country": "BR", **extra}
    key = config.google_books_key()
    if key:
        params["key"] = key
    return params


async def _get(http: httpx.AsyncClient, path: str, params: dict, timeout: float) -> dict:
    try:
        response = await http.get(f"{BASE_URL}{path}", params=_params(params), timeout=timeout)
    except httpx.HTTPError as exc:
        raise MediaSourceError(f"Google Books indisponível: {exc}") from exc

    if response.status_code == 404:
        return {}
    if response.status_code != 200:
        # 403 aqui costuma ser rateLimitExceeded/dailyLimitExceeded.
        raise MediaSourceError(f"Google Books respondeu {response.status_code}")

    try:
        return response.json()
    except ValueError as exc:
        raise MediaSourceError("Google Books devolveu JSON inválido") from exc


def _https(url: str | None) -> str | None:
    """A thumbnail vem em http://, que o React Native bloqueia por padrão."""
    if not url:
        return None
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    return truncate(url, URL_LIMIT)


class GoogleBooksClient:
    source = MediaSource.GOOGLE_BOOKS
    media_type = MediaType.LIVRO

    def normalize(self, raw: dict) -> NormalizedMedia:
        info = raw.get("volumeInfo") or {}
        title = clean_text(info.get("title")) or "Sem título"
        subtitle = clean_text(info.get("subtitle"))
        if subtitle:
            title = f"{title}: {subtitle}"

        images = info.get("imageLinks") or {}

        return NormalizedMedia(
            source=self.source,
            external_id=str(raw["id"]),
            media_type=self.media_type,
            title=truncate(title, TITLE_LIMIT),
            # Google Books não expõe título original.
            original_title=None,
            poster_url=_https(images.get("thumbnail") or images.get("smallThumbnail")),
            release_year=parse_year(info.get("publishedDate")),
            synopsis=strip_html(clean_text(info.get("description"))),
            raw_payload=raw,
        )

    async def search(
        self, http: httpx.AsyncClient, query: str, *, limit: int
    ) -> list[NormalizedMedia]:
        data = await _get(
            http,
            "/volumes",
            {"q": query, "maxResults": min(limit, 40)},
            config.search_timeout(),
        )
        items = data.get("items") or []
        return [self.normalize(raw) for raw in items[:limit] if raw.get("id")]

    async def fetch(self, http: httpx.AsyncClient, external_id: str) -> NormalizedMedia | None:
        data = await _get(http, f"/volumes/{external_id}", {}, config.fetch_timeout())
        if not data or not data.get("id"):
            return None
        return self.normalize(data)


CLIENT = GoogleBooksClient()
