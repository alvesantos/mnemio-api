"""Regras de status e progresso compartilhadas pelas quatro mídias."""


def test_media_starts_as_plano(client, auth_headers):
    response = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "plano"
    assert body["pages_read"] == 0
    assert body["chapters_done"] == 0
    assert body["finished_at"] is None


def test_creating_with_progress_moves_to_andamento(client, auth_headers):
    response = client.post(
        "/livros/", json={"title": "Duna", "pages_read": 1}, headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "andamento"


def test_updating_pages_moves_plano_to_andamento(client, auth_headers):
    livro = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers).json()
    assert livro["status"] == "plano"

    response = client.put(
        f"/livros/{livro['id']}", json={"pages_read": 12}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "andamento"


def test_chapters_alone_also_moves_to_andamento(client, auth_headers):
    livro = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers).json()
    response = client.put(
        f"/livros/{livro['id']}", json={"chapters_done": 3}, headers=auth_headers
    )
    assert response.json()["status"] == "andamento"


def test_episodes_move_serie_to_andamento(client, auth_headers):
    serie = client.post("/series/", json={"title": "Severance"}, headers=auth_headers).json()
    response = client.put(
        f"/series/{serie['id']}", json={"episodes_watched": 1}, headers=auth_headers
    )
    assert response.json()["status"] == "andamento"


def test_finalizado_stamps_finished_at(client, auth_headers):
    filme = client.post("/filmes/", json={"title": "Arrival"}, headers=auth_headers).json()
    assert filme["finished_at"] is None

    response = client.put(
        f"/filmes/{filme['id']}", json={"status": "finalizado"}, headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["finished_at"] is not None


def test_leaving_finalizado_clears_finished_at(client, auth_headers):
    filme = client.post(
        "/filmes/", json={"title": "Arrival", "status": "finalizado"}, headers=auth_headers
    ).json()
    assert filme["finished_at"] is not None

    response = client.put(
        f"/filmes/{filme['id']}", json={"status": "andamento"}, headers=auth_headers
    )
    assert response.json()["finished_at"] is None


def test_progress_does_not_downgrade_finalizado(client, auth_headers):
    livro = client.post(
        "/livros/",
        json={"title": "Duna", "status": "finalizado", "pages_read": 400},
        headers=auth_headers,
    ).json()
    assert livro["status"] == "finalizado"

    response = client.put(f"/livros/{livro['id']}", json={"pages_read": 410}, headers=auth_headers)
    assert response.json()["status"] == "finalizado"


def test_progress_does_not_revive_dropado(client, auth_headers):
    serie = client.post(
        "/series/", json={"title": "Lost", "status": "dropado"}, headers=auth_headers
    ).json()

    response = client.put(
        f"/series/{serie['id']}", json={"episodes_watched": 5}, headers=auth_headers
    )
    assert response.json()["status"] == "dropado"


def test_notes_are_saved(client, auth_headers):
    anime = client.post(
        "/animes/",
        json={"title": "Frieren", "notes": "Ritmo lento, mas vale muito."},
        headers=auth_headers,
    ).json()
    assert anime["notes"] == "Ritmo lento, mas vale muito."


def test_rejects_unknown_status(client, auth_headers):
    response = client.post(
        "/filmes/", json={"title": "Arrival", "status": "assistindo"}, headers=auth_headers
    )
    assert response.status_code == 422


def test_rejects_negative_progress(client, auth_headers):
    response = client.post(
        "/livros/", json={"title": "Duna", "pages_read": -1}, headers=auth_headers
    )
    assert response.status_code == 422


def test_filme_has_no_progress_fields(client, auth_headers):
    filme = client.post("/filmes/", json={"title": "Arrival"}, headers=auth_headers).json()
    assert "pages_read" not in filme
    assert "episodes_watched" not in filme
