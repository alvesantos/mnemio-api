def test_create_filme(client, auth_headers):
    response = client.post(
        "/filmes/", json={"title": "Arrival", "rating": 5}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Arrival"
    assert body["rating"] == 5


def test_create_filme_without_rating(client, auth_headers):
    response = client.post("/filmes/", json={"title": "Arrival"}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["rating"] is None


def test_create_filme_requires_auth(client):
    response = client.post("/filmes/", json={"title": "Arrival"})
    assert response.status_code == 401


def test_create_filme_rejects_invalid_rating(client, auth_headers):
    response = client.post(
        "/filmes/", json={"title": "Arrival", "rating": 5.5}, headers=auth_headers
    )
    assert response.status_code == 422


def test_create_filme_rejects_empty_title(client, auth_headers):
    response = client.post("/filmes/", json={"title": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_list_filmes(client, auth_headers):
    client.post("/filmes/", json={"title": "Arrival"}, headers=auth_headers)
    client.post("/filmes/", json={"title": "Dune"}, headers=auth_headers)

    response = client.get("/filmes/", headers=auth_headers)
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["Arrival", "Dune"]


def test_get_filme(client, auth_headers):
    created = client.post("/filmes/", json={"title": "Arrival"}, headers=auth_headers).json()

    response = client.get(f"/filmes/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Arrival"


def test_get_filme_not_found(client, auth_headers):
    response = client.get("/filmes/999", headers=auth_headers)
    assert response.status_code == 404


def test_update_filme(client, auth_headers):
    created = client.post("/filmes/", json={"title": "Arrival"}, headers=auth_headers).json()

    response = client.put(
        f"/filmes/{created['id']}", json={"rating": 4}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rating"] == 4
    assert body["title"] == "Arrival"


def test_update_filme_not_found(client, auth_headers):
    response = client.put("/filmes/999", json={"rating": 5}, headers=auth_headers)
    assert response.status_code == 404


def test_delete_filme(client, auth_headers):
    created = client.post("/filmes/", json={"title": "Arrival"}, headers=auth_headers).json()

    response = client.delete(f"/filmes/{created['id']}", headers=auth_headers)
    assert response.status_code == 204

    response = client.get(f"/filmes/{created['id']}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_filme_not_found(client, auth_headers):
    response = client.delete("/filmes/999", headers=auth_headers)
    assert response.status_code == 404


def test_filmes_are_isolated_per_user(client, auth_headers):
    client.post("/filmes/", json={"title": "Arrival"}, headers=auth_headers)

    client.post(
        "/auth/register",
        json={"name": "Other User", "email": "other@example.com", "password": "senha1234"},
    )
    other_login = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "senha1234"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get("/filmes/", headers=other_headers)
    assert response.status_code == 200
    assert response.json() == []
