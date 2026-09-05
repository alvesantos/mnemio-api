def test_create_livro(client, auth_headers):
    response = client.post(
        "/livros/", json={"title": "Duna", "rating": 4.5}, headers=auth_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Duna"
    assert body["rating"] == 4.5
    assert "id" in body


def test_create_livro_without_rating(client, auth_headers):
    response = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["rating"] is None


def test_create_livro_requires_auth(client):
    response = client.post("/livros/", json={"title": "Duna"})
    assert response.status_code == 401


def test_create_livro_rejects_invalid_rating(client, auth_headers):
    response = client.post(
        "/livros/", json={"title": "Duna", "rating": 6}, headers=auth_headers
    )
    assert response.status_code == 422


def test_create_livro_rejects_empty_title(client, auth_headers):
    response = client.post("/livros/", json={"title": ""}, headers=auth_headers)
    assert response.status_code == 422


def test_list_livros(client, auth_headers):
    client.post("/livros/", json={"title": "Duna"}, headers=auth_headers)
    client.post("/livros/", json={"title": "1984"}, headers=auth_headers)

    response = client.get("/livros/", headers=auth_headers)
    assert response.status_code == 200
    titles = [item["title"] for item in response.json()]
    assert titles == ["Duna", "1984"]


def test_get_livro(client, auth_headers):
    created = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers).json()

    response = client.get(f"/livros/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Duna"


def test_get_livro_not_found(client, auth_headers):
    response = client.get("/livros/999", headers=auth_headers)
    assert response.status_code == 404


def test_update_livro(client, auth_headers):
    created = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers).json()

    response = client.put(
        f"/livros/{created['id']}", json={"rating": 5}, headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rating"] == 5
    assert body["title"] == "Duna"


def test_update_livro_title(client, auth_headers):
    created = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers).json()

    response = client.put(
        f"/livros/{created['id']}",
        json={"title": "Duna Messias"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Duna Messias"


def test_update_livro_not_found(client, auth_headers):
    response = client.put("/livros/999", json={"rating": 5}, headers=auth_headers)
    assert response.status_code == 404


def test_delete_livro(client, auth_headers):
    created = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers).json()

    response = client.delete(f"/livros/{created['id']}", headers=auth_headers)
    assert response.status_code == 204

    response = client.get(f"/livros/{created['id']}", headers=auth_headers)
    assert response.status_code == 404


def test_delete_livro_not_found(client, auth_headers):
    response = client.delete("/livros/999", headers=auth_headers)
    assert response.status_code == 404


def test_livros_are_isolated_per_user(client, auth_headers):
    client.post("/livros/", json={"title": "Duna"}, headers=auth_headers)

    client.post(
        "/auth/register",
        json={"name": "Other User", "email": "other@example.com", "password": "senha1234"},
    )
    other_login = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "senha1234"}
    )
    other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

    response = client.get("/livros/", headers=other_headers)
    assert response.status_code == 200
    assert response.json() == []
