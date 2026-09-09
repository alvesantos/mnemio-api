"""Contrato comum das fontes externas e helpers de normalização.

Cada client traduz a resposta crua da sua API para NormalizedMedia — nada de
JSON de terceiro vazando para os routers ou para o banco.
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Protocol

import httpx


class MediaSourceError(Exception):
    """Falha ao falar com a fonte externa (timeout, 5xx, rate limit, resposta inesperada).

    Nunca vira 5xx para o app: o router degrada para o cache local.
    """


class MediaSourceUnconfigured(MediaSourceError):
    """Faltou a chave de API da fonte. O backend sobe assim mesmo, a busca é que não funciona."""


@dataclass(slots=True)
class NormalizedMedia:
    """Item de catálogo já traduzido para os campos de media_items."""

    source: str
    external_id: str
    media_type: str
    title: str
    original_title: str | None = None
    poster_url: str | None = None
    release_year: int | None = None
    synopsis: str | None = None
    raw_payload: dict | None = field(default=None, repr=False)

    def as_dict(self) -> dict:
        return asdict(self)


class MediaSourceClient(Protocol):
    """Interface que todo client de fonte implementa."""

    source: str
    media_type: str

    async def search(
        self, http: httpx.AsyncClient, query: str, *, limit: int
    ) -> list[NormalizedMedia]: ...

    async def fetch(
        self, http: httpx.AsyncClient, external_id: str
    ) -> NormalizedMedia | None: ...


_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def strip_html(text: str | None) -> str | None:
    """Limpa a sinopse.

    AniList devolve <br> e <i> mesmo com asHtml: false, e o Google Books manda
    HTML na description. O app renderiza texto puro.
    """
    if not text:
        return None
    cleaned = _BR_RE.sub("\n", text)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = (
        cleaned.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned).strip()
    return cleaned or None


_YEAR_RE = re.compile(r"(\d{4})")


def parse_year(value: str | int | None) -> int | None:
    """Extrai o ano de formatos variados.

    TMDB manda "2024-02-27" (ou "" para título sem data anunciada); o Google
    Books manda "2011", "2011-07" ou "2011-07-12".
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1000 <= value <= 2999 else None
    match = _YEAR_RE.search(value)
    if not match:
        return None
    year = int(match.group(1))
    return year if 1000 <= year <= 2999 else None


def clean_text(value: str | None) -> str | None:
    """Normaliza string vazia para None — sinopse em branco é comum no TMDB pt-BR."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def truncate(value: str | None, limit: int) -> str | None:
    """Corta no limite da coluna. Título e URL vêm de terceiros, sem garantia de tamanho."""
    if value is None:
        return None
    return value[:limit]
