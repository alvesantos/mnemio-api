"""Vínculo entre a avaliação do usuário e o item do catálogo."""

from app import media_cache
from app.media_sources.base import MediaSourceError
from app.models import Filme, MediaItem, PendingMediaLink

from tests.test_busca import make_media
from tests.test_media_cache import insert_cached


def test_create_links_to_cached_item(client, auth_headers, db):
    cached = insert_cached(db)

    response = client.post(
        "/filmes/",
        json={
            "title": "Duna: Parte 2",
            "rating": 5,
            "media_ref": {"source": "tmdb", "external_id": "693134"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["media_id"] == cached.id
    assert db.query(PendingMediaLink).count() == 0


def test_create_without_media_ref_still_works(client, auth_headers, db):
    """Cadastro manual continua existindo, sem catálogo nenhum."""
    response = client.post("/filmes/", json={"title": "Um filme qualquer"}, headers=auth_headers)

    assert response.status_code == 201
    assert response.json()["media_id"] is None
    assert db.query(MediaItem).count() == 0


def test_create_with_uncached_ref_resolves_in_background(client, auth_headers, fake_source, db):
    source = fake_source("filmes")
    source.fetch_result = make_media("693134", "Duna: Parte 2")

    response = client.post(
        "/filmes/",
        json={"title": "Duna: Parte 2", "media_ref": {"source": "tmdb", "external_id": "693134"}},
        headers=auth_headers,
    )

    # A resposta não espera o catálogo: sai na hora, sem vínculo...
    assert response.status_code == 201
    assert response.json()["media_id"] is None

    # ...e a varredura logo depois grava o item e refaz o vínculo.
    db.expire_all()
    item = db.query(Filme).one()
    assert item.media_id is not None
    assert db.query(MediaItem).one().title == "Duna: Parte 2"
    assert db.query(PendingMediaLink).count() == 0


def test_source_down_does_not_break_the_rating(client, auth_headers, fake_source, db):
    """A nota do usuário é o dado importante; o metadado é recuperável."""
    source = fake_source("filmes")
    source.error = MediaSourceError("timeout")

    response = client.post(
        "/filmes/",
        json={
            "title": "Duna: Parte 2",
            "rating": 4.5,
            "media_ref": {"source": "tmdb", "external_id": "693134"},
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["rating"] == 4.5

    db.expire_all()
    pending = db.query(PendingMediaLink).one()
    assert pending.external_id == "693134"
    assert pending.attempts == 1
    assert db.query(Filme).one().media_id is None


def test_pending_link_is_retried_on_the_next_request(client, auth_headers, fake_source, db):
    source = fake_source("filmes")
    source.error = MediaSourceError("timeout")

    client.post(
        "/filmes/",
        json={"title": "Duna: Parte 2", "media_ref": {"source": "tmdb", "external_id": "693134"}},
        headers=auth_headers,
    )
    db.expire_all()
    assert db.query(PendingMediaLink).count() == 1

    # A fonte volta; qualquer listagem do usuário dispara a varredura.
    source.error = None
    source.fetch_result = make_media("693134", "Duna: Parte 2")
    # attempts=1 e last_attempt_at recém-gravado: o backoff é encurtado no teste.
    pending = db.query(PendingMediaLink).one()
    pending.last_attempt_at = None
    db.commit()

    client.get("/filmes/", headers=auth_headers)

    db.expire_all()
    assert db.query(PendingMediaLink).count() == 0
    assert db.query(Filme).one().media_id == db.query(MediaItem).one().id


def test_pending_link_gives_up_after_max_attempts(client, auth_headers, fake_source, db):
    source = fake_source("filmes")
    source.error = MediaSourceError("timeout")

    client.post(
        "/filmes/",
        json={"title": "Duna: Parte 2", "media_ref": {"source": "tmdb", "external_id": "693134"}},
        headers=auth_headers,
    )

    db.expire_all()
    pending = db.query(PendingMediaLink).one()
    pending.attempts = media_cache.MAX_ATTEMPTS
    pending.last_attempt_at = None
    db.commit()

    calls_before = source.fetch_calls
    client.get("/filmes/", headers=auth_headers)

    # Para de tentar em vez de bater na fonte para sempre.
    assert source.fetch_calls == calls_before
    db.expire_all()
    assert db.query(PendingMediaLink).count() == 1
