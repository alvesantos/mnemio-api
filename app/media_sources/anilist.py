"""AniList — animes. GraphQL, endpoint único, sem autenticação para leitura.

É a fonte com o rate limit mais apertado (documentado 90 req/min por IP, mas a
API opera degradada em 30 há bastante tempo). O cache de busca e o debounce do
app são o que seguram isso.
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

ENDPOINT = "https://graphql.anilist.co"

TITLE_LIMIT = 300
URL_LIMIT = 500

MEDIA_FIELDS = """
  id
  title { romaji english native }
  coverImage { large }
  startDate { year }
  description(asHtml: false)
  episodes
  format
  status
"""

SEARCH_QUERY = """
query ($search: String, $perPage: Int) {
  Page(page: 1, perPage: $perPage) {
    media(search: $search, type: ANIME, sort: SEARCH_MATCH) {
      %s
    }
  }
}
""" % MEDIA_FIELDS

FETCH_QUERY = """
query ($id: Int) {
  Media(id: $id, type: ANIME) {
    %s
  }
}
""" % MEDIA_FIELDS


async def _post(http: httpx.AsyncClient, query: str, variables: dict, timeout: float) -> dict:
    try:
        response = await http.post(
            ENDPOINT,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        raise MediaSourceError(f"AniList indisponível: {exc}") from exc

    if response.status_code == 404:
        return {}
    if response.status_code != 200:
        raise MediaSourceError(f"AniList respondeu {response.status_code}")

    try:
        body = response.json()
    except ValueError as exc:
        raise MediaSourceError("AniList devolveu JSON inválido") from exc

    # GraphQL responde 200 com "errors" quando o id não existe.
    if body.get("errors") and not body.get("data"):
        raise MediaSourceError(f"AniList devolveu erro: {body['errors']}")

    return body.get("data") or {}


def remaining_requests(response: httpx.Response) -> int | None:
    """Quanto sobrou da janela de rate limit, quando a fonte informa."""
    raw = response.headers.get("X-RateLimit-Remaining")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


class AnilistClient:
    source = MediaSource.ANILIST
    media_type = MediaType.ANIME

    def normalize(self, raw: dict) -> NormalizedMedia:
        titles = raw.get("title") or {}
        # english vem null com frequência; romaji é o fallback confiável.
        title = truncate(
            clean_text(titles.get("english")) or clean_text(titles.get("romaji")) or "Sem título",
            TITLE_LIMIT,
        )
        native = clean_text(titles.get("native"))
        cover = (raw.get("coverImage") or {}).get("large")
        start = raw.get("startDate") or {}

        return NormalizedMedia(
            source=self.source,
            external_id=str(raw["id"]),
            media_type=self.media_type,
            title=title,
            original_title=truncate(native, TITLE_LIMIT) if native and native != title else None,
            poster_url=truncate(cover, URL_LIMIT),
            release_year=parse_year(start.get("year")),
            synopsis=strip_html(raw.get("description")),
            raw_payload=raw,
        )

    async def search(
        self, http: httpx.AsyncClient, query: str, *, limit: int
    ) -> list[NormalizedMedia]:
        data = await _post(
            http,
            SEARCH_QUERY,
            {"search": query, "perPage": limit},
            config.search_timeout(),
        )
        media = ((data.get("Page") or {}).get("media")) or []
        return [self.normalize(raw) for raw in media if raw]

    async def fetch(self, http: httpx.AsyncClient, external_id: str) -> NormalizedMedia | None:
        try:
            numeric_id = int(external_id)
        except ValueError:
            return None

        try:
            data = await _post(http, FETCH_QUERY, {"id": numeric_id}, config.fetch_timeout())
        except MediaSourceError as exc:
            # id inexistente devolve 200 + errors; tratar como "não encontrado"
            # em vez de derrubar a request.
            if "Not Found" in str(exc):
                return None
            raise

        raw = data.get("Media")
        return self.normalize(raw) if raw else None


CLIENT = AnilistClient()
