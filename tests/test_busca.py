"""Busca em tempo real: fonte externa, cache de curta duração e degradação."""

from datetime import datetime, timezone

from app.media_sources.base import MediaSourceError, NormalizedMedia
from app.models import MediaItem


def make_media(external_id="1", title="Duna", **kwargs):
    return NormalizedMedia(
        source=kwargs.pop("source", "tmdb"),
        external_id=external_id,
        media_type=kwargs.pop("media_type", "filme"),
        title=title,
        release_year=kwargs.pop("release_year", 2024),
        synopsis=kwargs.pop("synopsis", "Sinopse."),
        **kwargs,
    )


def test_busca_requires_auth(client):
    assert client.get("/busca", params={"q": "duna", "tipo": "filmes"}).status_code == 401


def test_busca_returns_normalized_results(client, auth_headers, fake_source):
    source = fake_source("filmes")
    source.search_results = [make_media("693134", "Duna: Parte 2")]

    response = client.get("/busca", params={"q": "duna", "tipo": "filmes"}, headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["external_id"] == "693134"
    assert body[0]["title"] == "Duna: Parte 2"
    assert body[0]["media_type"] == "filme"
    # Busca não persiste nada: o item ainda não está no cache.
    assert body[0]["cached"] is False
    assert body[0]["media_id"] is None


def test_busca_ignores_query_too_short(client, auth_headers, fake_source):
    source = fake_source("filmes")
    source.search_results = [make_media()]

    response = client.get("/busca", params={"q": "d", "tipo": "filmes"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []
    # Nem chega a chamar a fonte.
    assert source.search_calls == 0


def test_busca_marks_items_already_cached(client, auth_headers, fake_source, db):
    db.add(
        MediaItem(
            source="tmdb",
            external_id="693134",
            media_type="filme",
            title="Duna: Parte 2",
            refreshed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    source = fake_source("filmes")
    source.search_results = [make_media("693134"), make_media("999", "Outro")]

    body = client.get(
        "/busca", params={"q": "duna", "tipo": "filmes"}, headers=auth_headers
    ).json()

    cached = {item["external_id"]: item for item in body}
    assert cached["693134"]["cached"] is True
    assert cached["693134"]["media_id"] is not None
    assert cached["999"]["cached"] is False


def test_busca_does_not_persist_results(client, auth_headers, fake_source, db):
    source = fake_source("filmes")
    source.search_results = [make_media("693134")]

    client.get("/busca", params={"q": "duna", "tipo": "filmes"}, headers=auth_headers)

    assert db.query(MediaItem).count() == 0


def test_busca_reuses_short_lived_cache(client, auth_headers, fake_source):
    source = fake_source("filmes")
    source.search_results = [make_media()]

    for _ in range(3):
        client.get("/busca", params={"q": "duna", "tipo": "filmes"}, headers=auth_headers)

    assert source.search_calls == 1


def test_busca_falls_back_to_local_cache_when_source_is_down(
    client, auth_headers, fake_source, db
):
    db.add(
        MediaItem(
            source="tmdb",
            external_id="693134",
            media_type="filme",
            title="Duna: Parte 2",
            refreshed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    source = fake_source("filmes")
    source.error = MediaSourceError("timeout")

    response = client.get(
        "/busca", params={"q": "duna", "tipo": "filmes"}, headers=auth_headers
    )

    # Nunca 5xx: o usuário continua buscando, só com resultado limitado.
    assert response.status_code == 200
    assert response.headers["X-Search-Degraded"] == "true"
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Duna: Parte 2"
    assert body[0]["cached"] is True


def test_busca_returns_empty_when_source_is_down_and_cache_is_empty(
    client, auth_headers, fake_source
):
    source = fake_source("filmes")
    source.error = MediaSourceError("timeout")

    response = client.get(
        "/busca", params={"q": "duna", "tipo": "filmes"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == []
    assert response.headers["X-Search-Degraded"] == "true"


def test_busca_opens_circuit_breaker_after_repeated_failures(client, auth_headers, fake_source):
    source = fake_source("filmes")
    source.error = MediaSourceError("timeout")

    for index in range(7):
        client.get(
            "/busca", params={"q": f"duna {index}", "tipo": "filmes"}, headers=auth_headers
        )

    # Depois de 5 falhas a fonte é pulada por 30s em vez de acumular timeouts.
    assert source.search_calls == 5


def test_busca_rejects_unknown_type(client, auth_headers):
    response = client.get(
        "/busca", params={"q": "duna", "tipo": "quadrinhos"}, headers=auth_headers
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# Tipos sem fonte externa (hoje: animes, enquanto a AniList estiver desativada)
# --------------------------------------------------------------------------


def test_busca_de_anime_avisa_que_nao_ha_fonte(client, auth_headers):
    response = client.get("/busca", params={"q": "frieren", "tipo": "animes"}, headers=auth_headers)

    # Resposta clara em vez de lista vazia: o app manda o usuário para o
    # cadastro manual.
    assert response.status_code == 400
    assert "manualmente" in response.json()["detail"]


def test_detalhe_de_anime_avisa_que_nao_ha_fonte(client, auth_headers):
    response = client.get("/midias/animes/anilist/154587", headers=auth_headers)
    assert response.status_code == 400


def test_anime_continua_com_cadastro_manual(client, auth_headers):
    response = client.post("/animes/", json={"title": "Frieren", "rating": 5}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["title"] == "Frieren"
