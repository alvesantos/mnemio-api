"""Streak, conquistas, /me/stats e /me/continue."""

from datetime import date, timedelta

import pytest

from app.models import User
from app.stats import touch_activity


# --------------------------------------------------------------------------
# Streak — testado direto na função, para poder controlar a data
# --------------------------------------------------------------------------


def make_user(**kwargs) -> User:
    return User(
        name="X",
        email="x@example.com",
        hashed_password="x",
        streak_count=kwargs.get("streak_count", 0),
        longest_streak=kwargs.get("longest_streak", 0),
        last_activity_date=kwargs.get("last_activity_date"),
    )


def test_first_activity_starts_streak_at_one():
    user = make_user()
    touch_activity(user, today=date(2026, 1, 10))
    assert user.streak_count == 1
    assert user.longest_streak == 1
    assert user.last_activity_date == date(2026, 1, 10)


def test_consecutive_day_increments_streak():
    user = make_user(streak_count=3, longest_streak=3, last_activity_date=date(2026, 1, 9))
    touch_activity(user, today=date(2026, 1, 10))
    assert user.streak_count == 4
    assert user.longest_streak == 4


def test_same_day_does_not_inflate_streak():
    user = make_user(streak_count=3, longest_streak=3, last_activity_date=date(2026, 1, 10))
    touch_activity(user, today=date(2026, 1, 10))
    assert user.streak_count == 3


def test_skipped_day_resets_streak_to_one():
    user = make_user(streak_count=9, longest_streak=9, last_activity_date=date(2026, 1, 1))
    touch_activity(user, today=date(2026, 1, 10))
    assert user.streak_count == 1


def test_longest_streak_survives_a_reset():
    user = make_user(streak_count=9, longest_streak=9, last_activity_date=date(2026, 1, 1))
    touch_activity(user, today=date(2026, 1, 10))
    assert user.longest_streak == 9


@pytest.mark.parametrize("gap", [2, 5, 30])
def test_any_gap_larger_than_one_day_resets(gap):
    start = date(2026, 1, 10)
    user = make_user(streak_count=4, longest_streak=4, last_activity_date=start)
    touch_activity(user, today=start + timedelta(days=gap))
    assert user.streak_count == 1


# --------------------------------------------------------------------------
# /me/stats
# --------------------------------------------------------------------------


def test_stats_requires_auth(client):
    assert client.get("/me/stats").status_code == 401


def test_stats_start_empty(client, auth_headers):
    body = client.get("/me/stats", headers=auth_headers).json()
    assert body["total"] == 0
    assert body["finished"] == 0
    assert body["streak_count"] == 0
    assert all(not a["unlocked"] for a in body["achievements"])


def test_stats_catalog_is_always_complete(client, auth_headers):
    from app.achievements import CATALOG

    body = client.get("/me/stats", headers=auth_headers).json()
    assert len(body["achievements"]) == len(CATALOG)


def test_creating_item_starts_streak(client, auth_headers):
    client.post("/livros/", json={"title": "Duna"}, headers=auth_headers)
    body = client.get("/me/stats", headers=auth_headers).json()
    assert body["streak_count"] == 1
    assert body["total"] == 1


def test_stats_count_by_type(client, auth_headers):
    client.post("/livros/", json={"title": "Duna", "status": "finalizado"}, headers=auth_headers)
    client.post("/filmes/", json={"title": "Arrival", "status": "finalizado"}, headers=auth_headers)
    client.post("/series/", json={"title": "Lost", "status": "dropado"}, headers=auth_headers)

    body = client.get("/me/stats", headers=auth_headers).json()
    assert body["finished"] == 2
    assert body["finished_by_type"]["livros"] == 1
    assert body["finished_by_type"]["filmes"] == 1
    assert body["dropped"] == 1


def test_stats_are_isolated_per_user(client, auth_headers):
    client.post("/livros/", json={"title": "Duna"}, headers=auth_headers)

    client.post(
        "/auth/register",
        json={"name": "Outro", "email": "outro@example.com", "password": "senha1234"},
    )
    other = client.post(
        "/auth/login", json={"email": "outro@example.com", "password": "senha1234"}
    ).json()["access_token"]

    body = client.get("/me/stats", headers={"Authorization": f"Bearer {other}"}).json()
    assert body["total"] == 0


# --------------------------------------------------------------------------
# Conquistas
# --------------------------------------------------------------------------


def test_first_finished_unlocks_primeira_vez(client, auth_headers):
    response = client.post(
        "/filmes/", json={"title": "Arrival", "status": "finalizado"}, headers=auth_headers
    )
    codes = [a["code"] for a in response.json()["unlocked_achievements"]]
    assert "primeira_vez" in codes


def test_achievement_is_returned_only_once(client, auth_headers):
    client.post("/filmes/", json={"title": "Arrival", "status": "finalizado"}, headers=auth_headers)
    second = client.post(
        "/filmes/", json={"title": "Sicario", "status": "finalizado"}, headers=auth_headers
    )
    codes = [a["code"] for a in second.json()["unlocked_achievements"]]
    assert "primeira_vez" not in codes


def test_unlocking_via_update_is_reported(client, auth_headers):
    livro = client.post("/livros/", json={"title": "Duna"}, headers=auth_headers).json()
    assert livro["unlocked_achievements"] == []

    response = client.put(
        f"/livros/{livro['id']}", json={"status": "finalizado"}, headers=auth_headers
    )
    codes = [a["code"] for a in response.json()["unlocked_achievements"]]
    assert "primeira_vez" in codes


def test_leitor_nato_unlocks_at_ten_books(client, auth_headers):
    codes = []
    for index in range(10):
        response = client.post(
            "/livros/",
            json={"title": f"Livro {index}", "status": "finalizado"},
            headers=auth_headers,
        )
        codes = [a["code"] for a in response.json()["unlocked_achievements"]]

    assert "leitor_nato" in codes

    body = client.get("/me/stats", headers=auth_headers).json()
    unlocked = {a["code"] for a in body["achievements"] if a["unlocked"]}
    assert "leitor_nato" in unlocked


def test_locked_achievement_reports_progress(client, auth_headers):
    for index in range(3):
        client.post(
            "/livros/",
            json={"title": f"Livro {index}", "status": "finalizado"},
            headers=auth_headers,
        )

    body = client.get("/me/stats", headers=auth_headers).json()
    leitor = next(a for a in body["achievements"] if a["code"] == "leitor_nato")
    assert leitor["unlocked"] is False
    assert leitor["progress"] == 3
    assert leitor["target"] == 10


def test_reads_do_not_return_achievements(client, auth_headers):
    client.post("/filmes/", json={"title": "Arrival", "status": "finalizado"}, headers=auth_headers)
    listed = client.get("/filmes/", headers=auth_headers).json()
    assert listed[0]["unlocked_achievements"] == []


# --------------------------------------------------------------------------
# /me/continue
# --------------------------------------------------------------------------


def test_continue_requires_auth(client):
    assert client.get("/me/continue").status_code == 401


def test_continue_is_empty_without_progress(client, auth_headers):
    client.post("/livros/", json={"title": "Duna"}, headers=auth_headers)
    assert client.get("/me/continue", headers=auth_headers).json() == []


def test_continue_lists_only_andamento(client, auth_headers):
    client.post("/livros/", json={"title": "Em andamento", "pages_read": 10}, headers=auth_headers)
    client.post("/livros/", json={"title": "No plano"}, headers=auth_headers)
    client.post("/filmes/", json={"title": "Feito", "status": "finalizado"}, headers=auth_headers)

    body = client.get("/me/continue", headers=auth_headers).json()
    assert [item["title"] for item in body] == ["Em andamento"]


def test_continue_mixes_types_and_exposes_progress(client, auth_headers):
    client.post(
        "/livros/",
        json={"title": "Duna", "pages_read": 120, "total_pages": 600},
        headers=auth_headers,
    )
    client.post(
        "/series/",
        json={"title": "Severance", "episodes_watched": 4, "total_episodes": 9},
        headers=auth_headers,
    )

    body = client.get("/me/continue", headers=auth_headers).json()
    by_type = {item["type"]: item for item in body}

    assert by_type["livros"]["progress_current"] == 120
    assert by_type["livros"]["progress_total"] == 600
    assert by_type["livros"]["progress_label"] == "páginas"
    assert by_type["series"]["progress_current"] == 4
    assert by_type["series"]["progress_label"] == "episódios"


def test_continue_is_isolated_per_user(client, auth_headers):
    client.post("/livros/", json={"title": "Meu", "pages_read": 5}, headers=auth_headers)

    client.post(
        "/auth/register",
        json={"name": "Outro", "email": "outro@example.com", "password": "senha1234"},
    )
    other = client.post(
        "/auth/login", json={"email": "outro@example.com", "password": "senha1234"}
    ).json()["access_token"]

    body = client.get("/me/continue", headers={"Authorization": f"Bearer {other}"}).json()
    assert body == []
