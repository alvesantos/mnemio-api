"""Cache sob demanda: quando persiste, quando reconsulta e como não duplica."""

from datetime import datetime, timedelta, timezone

from app import media_cache
from app.media_sources.base import MediaSourceError, NormalizedMedia
from app.models import MediaItem

from tests.test_busca import make_media


def insert_cached(db, *, external_id="693134", title="Duna: Parte 2", age_days=0):
    moment = datetime.now(timezone.utc) - timedelta(days=age_days)
    item = MediaItem(
        source="tmdb",
        external_id=external_id,
        media_type="filme",
        title=title,
        refreshed_at=moment,
        created_at=moment,
        updated_at=moment,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


# --------------------------------------------------------------------------
# Upsert
# --------------------------------------------------------------------------


def test_upsert_creates_the_item(db):
    media_id = media_cache.upsert_media_item(db, make_media("693134", "Duna: Parte 2"))
    db.commit()

    row = db.query(MediaItem).one()
    assert row.id == media_id
    assert row.title == "Duna: Parte 2"
    assert row.source == "tmdb"


def test_upsert_is_idempotent(db):
    """Dois usuários adicionando o mesmo item geram uma linha só."""
    first = media_cache.upsert_media_item(db, make_media("693134", "Duna: Parte 2"))
    db.commit()
    second = media_cache.upsert_media_item(db, make_media("693134", "Duna: Parte 2"))
    db.commit()

    assert first == second
    assert db.query(MediaItem).count() == 1


def test_upsert_refreshes_the_existing_row(db):
    old = insert_cached(db, title="Título velho", age_days=90)
    old_refreshed_at = old.refreshed_at

    media_cache.upsert_media_item(db, make_media("693134", "Título novo"))
    db.commit()

    row = db.query(MediaItem).one()
    assert row.id == old.id
    assert row.title == "Título novo"
    assert row.refreshed_at > old_refreshed_at


def test_upsert_separates_items_by_source(db):
    media_cache.upsert_media_item(db, make_media("1", "Do TMDB", source="tmdb"))
    media_cache.upsert_media_item(
        db, make_media("1", "Do AniList", source="anilist", media_type="anime")
    )
    db.commit()

    assert db.query(MediaItem).count() == 2


def test_is_stale_respects_the_ttl(db):
    fresh = insert_cached(db, external_id="fresco", age_days=1)
    stale = insert_cached(db, external_id="vencido", age_days=60)

    assert media_cache.is_stale(fresh) is False
    assert media_cache.is_stale(stale) is True


# --------------------------------------------------------------------------
# Detalhe: /midias/{tipo}/{source}/{external_id}
# --------------------------------------------------------------------------


def test_detalhe_requires_auth(client):
    assert client.get("/midias/filmes/tmdb/693134").status_code == 401


def test_detalhe_fetches_and_persists_on_first_access(client, auth_headers, fake_source, db):
    source = fake_source("filmes")
    source.fetch_result = make_media("693134", "Duna: Parte 2")

    response = client.get("/midias/filmes/tmdb/693134", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["title"] == "Duna: Parte 2"
    # A resposta não espera a gravação, mas ela acontece logo depois.
    row = db.query(MediaItem).one()
    assert row.external_id == "693134"


def test_detalhe_serves_from_cache_without_touching_the_source(
    client, auth_headers, fake_source, db
):
    insert_cached(db)
    source = fake_source("filmes")

    response = client.get("/midias/filmes/tmdb/693134", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["cached"] is True
    assert source.fetch_calls == 0


def test_detalhe_serves_stale_item_and_refreshes_in_background(
    client, auth_headers, fake_source, db
):
    insert_cached(db, title="Título velho", age_days=60)
    source = fake_source("filmes")
    source.fetch_result = make_media("693134", "Título novo")

    response = client.get("/midias/filmes/tmdb/693134", headers=auth_headers)

    # O usuário recebe o que já estava no banco, sem esperar o refresh...
    assert response.json()["title"] == "Título velho"
    # ...que acontece logo em seguida.
    assert source.fetch_calls == 1
    db.expire_all()
    assert db.query(MediaItem).one().title == "Título novo"


def test_detalhe_returns_404_when_the_source_does_not_have_it(client, auth_headers, fake_source):
    source = fake_source("filmes")
    source.fetch_result = None

    assert client.get("/midias/filmes/tmdb/000", headers=auth_headers).status_code == 404


def test_detalhe_returns_503_when_the_source_is_down(client, auth_headers, fake_source):
    source = fake_source("filmes")
    source.error = MediaSourceError("timeout")

    assert client.get("/midias/filmes/tmdb/693134", headers=auth_headers).status_code == 503


def test_detalhe_rejects_source_that_does_not_serve_the_type(client, auth_headers, fake_source):
    fake_source("filmes")

    # TMDB atende filmes; anilist não.
    assert client.get("/midias/filmes/anilist/1", headers=auth_headers).status_code == 404


def test_failed_persistence_does_not_break_the_response(
    client, auth_headers, fake_source, monkeypatch, db
):
    """Gravar no cache é best-effort: falhar não pode virar erro visível."""
    source = fake_source("filmes")
    source.fetch_result = make_media("693134")

    def explode(*args, **kwargs):
        raise RuntimeError("banco fora")

    monkeypatch.setattr(media_cache, "upsert_media_item", explode)

    response = client.get("/midias/filmes/tmdb/693134", headers=auth_headers)

    assert response.status_code == 200
    assert db.query(MediaItem).count() == 0
