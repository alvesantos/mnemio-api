def test_create_serie(client, auth_headers):
    response = client.post(
        "/series/", json={"title": "Severance", "rating": 5}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Severance"
    assert body["rating"] == 5


def test_create_serie_without_rating(client, auth_headers):
    response = client.post("/series/", json={"title": "Severance"}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["rating"] is None


def test_create_serie_requires_auth(client):
    response = client.post("/series/", json={"title": "Severance"})
    assert response.status_code == 401


def test_create_serie_rejects_invalid_rating(client, auth_headers):
    response = client.post(
        "/series/", json={"title": "Severance", "rating": -1}, headers=auth_headers
    )
    assert response.status_code == 422


def test_create_serie_rejects_empty_title(client, auth_headers):
    response = client.post("/series/", json={"title": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_list_series(client, auth_headers):
    client.post("/series/", json={"title": "Severance"}, headers=auth_headers)
    client.post("/series/", json={"title": "Arcane"}, headers=auth_headers)

    response = client.get("/series/", headers=auth_headers)
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["Severance", "Arcane"]


def test_get_serie(client, auth_headers):
    created = client.post("/series/", json={"title": "Severance"}, headers=auth_headers).json()

    response = client.get(f"/series/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Severance"


def test_get_serie_not_found(client, auth_headers):
    response = client.get("/series/999", headers=auth_headers)
    assert response.status_code == 404


def test_update_serie(client, auth_headers):
    created = client.post("/series/", json={"title": "Severance"}, headers=auth_headers).json()

    response = client.put(
        f"/series/{created['id']}", json={"rating": 4.5}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rating"] == 4.5
    assert body["title"] == "Severance"


def test_update_serie_not_found(client, auth_headers):
    response = client.put("/series/999", json={"rating": 5}, headers=auth_headers)
    assert response.status_code == 404


def test_delete_serie(client, auth_headers):
    created = client.post("/series/", json={"title": "Severance"}, headers=auth_headers).json()

    response = client.delete(f"/series/{created['id']}", headers=auth_headers)
    assert response.status_code == 204

    response = client.get(f"/series/{created['id']}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_serie_not_found(client, auth_headers):
    response = client.delete("/series/999", headers=auth_headers)
    assert response.status_code == 404


def test_series_are_isolated_per_user(client, auth_headers):
    client.post("/series/", json={"title": "Severance"}, headers=auth_headers)

    client.post(
        "/auth/register",
        json={"name": "Other User", "email": "other@example.com", "password": "senha1234"},
    )
    other_login = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "senha1234"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get("/series/", headers=other_headers)
    assert response.status_code == 200
    assert response.json() == []
