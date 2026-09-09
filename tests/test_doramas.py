"""CRUD de doramas — mesmo contrato das outras mídias, com progresso em episódios."""


def test_create_dorama(client, auth_headers):
    response = client.post(
        "/doramas/",
        json={"title": "Round 6", "rating": 5, "total_episodes": 9},
        headers=auth_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Round 6"
    assert body["rating"] == 5
    assert body["total_episodes"] == 9
    assert body["episodes_watched"] == 0
    assert body["media_id"] is None


def test_create_dorama_requires_auth(client):
    assert client.post("/doramas/", json={"title": "Round 6"}).status_code == 401


def test_create_dorama_rejects_invalid_rating(client, auth_headers):
    response = client.post(
        "/doramas/", json={"title": "Round 6", "rating": 6}, headers=auth_headers
    )
    assert response.status_code == 422


def test_list_and_get_dorama(client, auth_headers):
    created = client.post("/doramas/", json={"title": "Pousando no Amor"}, headers=auth_headers)
    item_id = created.json()["id"]

    assert len(client.get("/doramas/", headers=auth_headers).json()) == 1
    assert client.get(f"/doramas/{item_id}", headers=auth_headers).json()["title"] == "Pousando no Amor"


def test_update_dorama_progress_moves_it_to_andamento(client, auth_headers):
    created = client.post("/doramas/", json={"title": "Round 6"}, headers=auth_headers)
    item_id = created.json()["id"]

    response = client.put(
        f"/doramas/{item_id}", json={"episodes_watched": 3}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "andamento"


def test_delete_dorama(client, auth_headers):
    created = client.post("/doramas/", json={"title": "Round 6"}, headers=auth_headers)
    item_id = created.json()["id"]

    assert client.delete(f"/doramas/{item_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/doramas/{item_id}", headers=auth_headers).status_code == 404


def test_doramas_are_isolated_per_user(client, auth_headers):
    client.post("/doramas/", json={"title": "Round 6"}, headers=auth_headers)

    client.post(
        "/auth/register",
        json={"name": "Outro", "email": "outro@example.com", "password": "senha1234"},
    )
    token = client.post(
        "/auth/login", json={"email": "outro@example.com", "password": "senha1234"}
    ).json()["access_token"]

    assert client.get("/doramas/", headers={"Authorization": f"Bearer {token}"}).json() == []


def test_doramas_count_in_stats(client, auth_headers):
    client.post(
        "/doramas/", json={"title": "Round 6", "status": "finalizado"}, headers=auth_headers
    )

    stats = client.get("/me/stats", headers=auth_headers).json()

    assert stats["finished_by_type"]["doramas"] == 1
    assert stats["finished"] == 1


def test_deleting_account_removes_doramas(client, auth_headers):
    client.post("/doramas/", json={"title": "Round 6"}, headers=auth_headers)

    assert client.delete("/auth/me", headers=auth_headers).status_code == 204
    assert client.get("/doramas/", headers=auth_headers).status_code == 401
