"""Configuração das integrações externas, lida do ambiente sob demanda.

Os getters são funções (e não constantes de módulo) de propósito: o
`load_dotenv()` de `app/main.py` e o `os.environ.setdefault` dos testes rodam
depois do import destes módulos, então ler no import congelaria valores
errados.
"""

import os

# Países de origem que classificam uma série do TMDB como dorama.
DEFAULT_DORAMA_COUNTRIES = "KR"


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def tmdb_token() -> str | None:
    """Token v4 (read access) do TMDB. Sem ele, filmes/séries/doramas não buscam."""
    return os.environ.get("TMDB_API_READ_ACCESS_TOKEN") or None


def google_books_key() -> str | None:
    """Opcional na API, mas sem chave a quota é por IP e estoura rápido."""
    return os.environ.get("GOOGLE_BOOKS_API_KEY") or None


def search_timeout() -> float:
    """Autocomplete: acima disso o usuário já desistiu."""
    return _float("MEDIA_SEARCH_TIMEOUT_SECONDS", 2.5)


def fetch_timeout() -> float:
    """Detalhe: tem tela de loading legítima."""
    return _float("MEDIA_FETCH_TIMEOUT_SECONDS", 3.0)


def refresh_timeout() -> float:
    """Background: ninguém está esperando."""
    return _float("MEDIA_REFRESH_TIMEOUT_SECONDS", 5.0)


def cache_ttl_days() -> int:
    return _int("MEDIA_CACHE_TTL_DAYS", 30)


def search_cache_ttl_seconds() -> int:
    return _int("MEDIA_SEARCH_CACHE_TTL_SECONDS", 60)


def dorama_origin_countries() -> frozenset[str]:
    raw = os.environ.get("DORAMA_ORIGIN_COUNTRIES") or DEFAULT_DORAMA_COUNTRIES
    return frozenset(code.strip().upper() for code in raw.split(",") if code.strip())
