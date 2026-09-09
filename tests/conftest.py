import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import media_cache, media_sources
from app.database import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# As tarefas de background abrem a própria sessão (a do request fecha junto com
# a resposta), então precisam apontar para o mesmo SQLite em memória do teste.
media_cache.SESSION_FACTORY = TestingSessionLocal


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_media_sources():
    """Cache de busca e circuit breaker vivem no processo: zerar entre testes."""
    media_sources._search_cache.clear()
    media_sources._breakers.clear()
    yield
    media_sources._search_cache.clear()
    media_sources._breakers.clear()


class FakeSourceClient:
    """Fonte externa controlada pelo teste.

    `search_results`/`fetch_result` são NormalizedMedia; `error` faz a fonte
    falhar como se estivesse fora do ar.
    """

    def __init__(self, source="tmdb", media_type="filme"):
        self.source = source
        self.media_type = media_type
        self.search_results = []
        self.fetch_result = None
        self.error = None
        self.search_calls = 0
        self.fetch_calls = 0

    async def search(self, http, query, *, limit):
        self.search_calls += 1
        if self.error:
            raise self.error
        return list(self.search_results)[:limit]

    async def fetch(self, http, external_id):
        self.fetch_calls += 1
        if self.error:
            raise self.error
        return self.fetch_result


@pytest.fixture
def fake_source(monkeypatch):
    """Instala uma fonte falsa no lugar do client real de um tipo de mídia."""

    def install(route_type="filmes", *, source="tmdb", media_type="filme"):
        fake = FakeSourceClient(source=source, media_type=media_type)
        monkeypatch.setitem(media_sources.CLIENTS, route_type, fake)
        return fake

    return install


@pytest.fixture
def db():
    """Sessão direta no mesmo banco do client, para montar e conferir estado."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    client.post(
        "/auth/register",
        json={"name": "Test User", "email": "test@example.com", "password": "senha1234"},
    )
    response = client.post(
        "/auth/login", json={"email": "test@example.com", "password": "senha1234"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
