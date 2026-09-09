"""Normalização das respostas de cada fonte externa."""

import pytest

from app.media_sources import anilist, google_books, tmdb
from app.media_sources.base import parse_year, strip_html


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2024-02-27", 2024),
        ("2011-07", 2011),
        ("2011", 2011),
        ("", None),
        (None, None),
        (2023, 2023),
        ("sem data", None),
    ],
)
def test_parse_year_accepts_every_format_the_sources_use(raw, expected):
    assert parse_year(raw) == expected


def test_strip_html_cleans_anilist_description():
    raw = "Linha um.<br><br>Linha <i>dois</i> &amp; três."
    assert strip_html(raw) == "Linha um.\n\nLinha dois & três."


def test_strip_html_turns_empty_into_none():
    assert strip_html("") is None
    assert strip_html("<br>") is None


# --------------------------------------------------------------------------
# TMDB
# --------------------------------------------------------------------------


def test_tmdb_movie_maps_fields():
    media = tmdb.MOVIE_CLIENT.normalize(
        {
            "id": 693134,
            "title": "Duna: Parte 2",
            "original_title": "Dune: Part Two",
            "poster_path": "/abc.jpg",
            "release_date": "2024-02-27",
            "overview": "Paul se une aos Fremen.",
        }
    )

    assert media.source == "tmdb"
    assert media.external_id == "693134"
    assert media.media_type == "filme"
    assert media.title == "Duna: Parte 2"
    assert media.original_title == "Dune: Part Two"
    assert media.poster_url == "https://image.tmdb.org/t/p/w342/abc.jpg"
    assert media.release_year == 2024
    assert media.synopsis == "Paul se une aos Fremen."


def test_tmdb_movie_without_poster_or_date():
    media = tmdb.MOVIE_CLIENT.normalize(
        {"id": 1, "title": "Sem nada", "poster_path": None, "release_date": "", "overview": ""}
    )
    assert media.poster_url is None
    assert media.release_year is None
    assert media.synopsis is None


def test_tmdb_keeps_original_title_only_when_it_differs():
    media = tmdb.MOVIE_CLIENT.normalize(
        {"id": 1, "title": "Oppenheimer", "original_title": "Oppenheimer"}
    )
    assert media.original_title is None


def test_tmdb_tv_korean_series_is_classified_as_dorama():
    raw = {
        "id": 93405,
        "name": "Round 6",
        "original_name": "오징어 게임",
        "origin_country": ["KR"],
        "first_air_date": "2021-09-17",
    }
    assert tmdb.DORAMA_CLIENT.matches(raw) is True
    assert tmdb.SERIE_CLIENT.matches(raw) is False
    assert tmdb.DORAMA_CLIENT.normalize(raw).media_type == "dorama"


def test_tmdb_tv_non_korean_series_stays_serie():
    raw = {"id": 1396, "name": "Breaking Bad", "origin_country": ["US"]}
    assert tmdb.SERIE_CLIENT.matches(raw) is True
    assert tmdb.DORAMA_CLIENT.matches(raw) is False
    assert tmdb.SERIE_CLIENT.normalize(raw).media_type == "serie"


def test_tmdb_tv_classifies_by_the_item_not_by_the_client():
    """Abrir uma série coreana pela rota de séries ainda grava dorama."""
    raw = {"id": 93405, "name": "Round 6", "origin_country": ["KR"]}
    assert tmdb.SERIE_CLIENT.normalize(raw).media_type == "dorama"


# --------------------------------------------------------------------------
# AniList
# --------------------------------------------------------------------------


def test_anilist_maps_fields_and_cleans_description():
    media = anilist.CLIENT.normalize(
        {
            "id": 154587,
            "title": {
                "english": "Frieren: Beyond Journey's End",
                "romaji": "Sousou no Frieren",
                "native": "葬送のフリーレン",
            },
            "coverImage": {"large": "https://s4.anilist.co/cover.jpg"},
            "startDate": {"year": 2023},
            "description": "A jornada <i>continua</i>.<br>De novo.",
        }
    )

    assert media.source == "anilist"
    assert media.external_id == "154587"
    assert media.media_type == "anime"
    assert media.title == "Frieren: Beyond Journey's End"
    assert media.original_title == "葬送のフリーレン"
    assert media.poster_url == "https://s4.anilist.co/cover.jpg"
    assert media.release_year == 2023
    assert media.synopsis == "A jornada continua.\nDe novo."


def test_anilist_falls_back_to_romaji_when_english_is_null():
    media = anilist.CLIENT.normalize(
        {"id": 1, "title": {"english": None, "romaji": "Sousou no Frieren", "native": None}}
    )
    assert media.title == "Sousou no Frieren"


def test_anilist_tolerates_missing_start_date():
    media = anilist.CLIENT.normalize({"id": 1, "title": {"romaji": "Anunciado"}, "startDate": {"year": None}})
    assert media.release_year is None


# --------------------------------------------------------------------------
# Google Books
# --------------------------------------------------------------------------


def test_google_books_maps_fields():
    media = google_books.CLIENT.normalize(
        {
            "id": "zyTCAlFPjgYC",
            "volumeInfo": {
                "title": "Mistborn",
                "subtitle": "The Final Empire",
                "publishedDate": "2006-07-17",
                "description": "<p>Um império de cinzas.</p>",
                "imageLinks": {"thumbnail": "http://books.google.com/capa.jpg"},
            },
        }
    )

    assert media.source == "google_books"
    assert media.external_id == "zyTCAlFPjgYC"
    assert media.media_type == "livro"
    assert media.title == "Mistborn: The Final Empire"
    assert media.release_year == 2006
    assert media.synopsis == "Um império de cinzas."
    # http:// é bloqueado pelo React Native.
    assert media.poster_url == "https://books.google.com/capa.jpg"


def test_google_books_handles_year_only_publish_date():
    media = google_books.CLIENT.normalize(
        {"id": "x", "volumeInfo": {"title": "Livro", "publishedDate": "2011"}}
    )
    assert media.release_year == 2011
    assert media.poster_url is None
