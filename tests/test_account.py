"""Página de privacidade e exclusão de conta (exigências do Google Play)."""


def register(client, email):
    client.post(
        "/auth/register",
        json={"name": "Alguem", "email": email, "password": "senha1234"},
    )
    token = client.post(
        "/auth/login", json={"email": email, "password": "senha1234"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_privacy_page_is_public(client):
    response = client.get("/privacidade")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_privacy_page_mentions_deletion(client):
    body = client.get("/privacidade").text
    assert "Excluir conta" in body


def test_delete_account_requires_auth(client):
    assert client.delete("/auth/me").status_code == 401


def test_delete_account_removes_user(client, auth_headers):
    assert client.delete("/auth/me", headers=auth_headers).status_code == 204
    # O token continua válido criptograficamente, mas o usuário sumiu.
    assert client.get("/auth/me", headers=auth_headers).status_code == 401


def test_delete_account_removes_all_media(client, auth_headers):
    for path in ("/livros", "/series", "/filmes", "/animes"):
        client.post(f"{path}/", json={"title": "X"}, headers=auth_headers)

    client.delete("/auth/me", headers=auth_headers)

    fresh = register(client, "novo@example.com")
    for path in ("/livros", "/series", "/filmes", "/animes"):
        assert client.get(f"{path}/", headers=fresh).json() == []


def test_delete_account_removes_achievements(client, auth_headers):
    client.post(
        "/filmes/", json={"title": "Arrival", "status": "finalizado"}, headers=auth_headers
    )
    assert client.delete("/auth/me", headers=auth_headers).status_code == 204

    # Mesmo e-mail recadastrado começa do zero, sem herdar conquistas.
    again = register(client, "test@example.com")
    body = client.get("/me/stats", headers=again).json()
    assert all(not a["unlocked"] for a in body["achievements"])


def test_delete_account_does_not_touch_other_users(client, auth_headers):
    other = register(client, "outro@example.com")
    client.post("/livros/", json={"title": "Do outro"}, headers=other)

    client.delete("/auth/me", headers=auth_headers)

    remaining = client.get("/livros/", headers=other).json()
    assert [item["title"] for item in remaining] == ["Do outro"]
    assert client.get("/auth/me", headers=other).status_code == 200
