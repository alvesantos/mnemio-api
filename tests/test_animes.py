def test_create_anime(client, auth_headers):
    response = client.post(
        "/animes/", json={"title": "Frieren", "rating": 5}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Frieren"
    assert body["rating"] == 5


def test_create_anime_without_rating(client, auth_headers):
    response = client.post("/animes/", json={"title": "Frieren"}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["rating"] is None


def test_create_anime_requires_auth(client):
    response = client.post("/animes/", json={"title": "Frieren"})
    assert response.status_code == 401


def test_create_anime_rejects_invalid_rating(client, auth_headers):
    response = client.post(
        "/animes/", json={"title": "Frieren", "rating": 10}, headers=auth_headers
    )
    assert response.status_code == 422


def test_create_anime_rejects_empty_title(client, auth_headers):
    response = client.post("/animes/", json={"title": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_list_animes(client, auth_headers):
    client.post("/animes/", json={"title": "Frieren"}, headers=auth_headers)
    client.post("/animes/", json={"title": "Vinland Saga"}, headers=auth_headers)

    response = client.get("/animes/", headers=auth_headers)
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["Frieren", "Vinland Saga"]


def test_get_anime(client, auth_headers):
    created = client.post("/animes/", json={"title": "Frieren"}, headers=auth_headers).json()

    response = client.get(f"/animes/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Frieren"


def test_get_anime_not_found(client, auth_headers):
    response = client.get("/animes/999", headers=auth_headers)
    assert response.status_code == 404


def test_update_anime(client, auth_headers):
    created = client.post("/animes/", json={"title": "Frieren"}, headers=auth_headers).json()

    response = client.put(
        f"/animes/{created['id']}", json={"rating": 4.5}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rating"] == 4.5
    assert body["title"] == "Frieren"


def test_update_anime_not_found(client, auth_headers):
    response = client.put("/animes/999", json={"rating": 5}, headers=auth_headers)
    assert response.status_code == 404


def test_delete_anime(client, auth_headers):
    created = client.post("/animes/", json={"title": "Frieren"}, headers=auth_headers).json()

    response = client.delete(f"/animes/{created['id']}", headers=auth_headers)
    assert response.status_code == 204

    response = client.get(f"/animes/{created['id']}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_anime_not_found(client, auth_headers):
    response = client.delete("/animes/999", headers=auth_headers)
    assert response.status_code == 404


def test_animes_are_isolated_per_user(client, auth_headers):
    client.post("/animes/", json={"title": "Frieren"}, headers=auth_headers)

    client.post(
        "/auth/register",
        json={"name": "Other User", "email": "other@example.com", "password": "senha1234"},
    )
    other_login = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "senha1234"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get("/animes/", headers=other_headers)
    assert response.status_code == 200
    assert response.json() == []
