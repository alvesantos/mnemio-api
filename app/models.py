from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.database import Base


class MediaSource:
    """Fonte externa de onde um item de catálogo veio."""

    TMDB = "tmdb"
    ANILIST = "anilist"
    GOOGLE_BOOKS = "google_books"

    ALL = (TMDB, ANILIST, GOOGLE_BOOKS)


class MediaType:
    """Tipo de mídia no catálogo, no singular.

    Dorama não é uma fonte própria: é uma série do TMDB cujo país de origem
    está em config.dorama_origin_countries().
    """

    FILME = "filme"
    SERIE = "serie"
    DORAMA = "dorama"
    ANIME = "anime"
    LIVRO = "livro"

    ALL = (FILME, SERIE, DORAMA, ANIME, LIVRO)


# As rotas e o app usam o plural ("filmes"); o catálogo guarda o singular.
# Os dois mapas existem para a tradução nunca ser feita na mão.
ROUTE_TO_MEDIA_TYPE = {
    "livros": MediaType.LIVRO,
    "series": MediaType.SERIE,
    "filmes": MediaType.FILME,
    "animes": MediaType.ANIME,
    "doramas": MediaType.DORAMA,
}

MEDIA_TYPE_TO_ROUTE = {value: key for key, value in ROUTE_TO_MEDIA_TYPE.items()}


class MediaStatus:
    """Status compartilhado por livros, séries, filmes e animes."""

    PLANO = "plano"
    ANDAMENTO = "andamento"
    FINALIZADO = "finalizado"
    DROPADO = "dropado"

    ALL = (PLANO, ANDAMENTO, FINALIZADO, DROPADO)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Sequência de dias consecutivos com atividade.
    streak_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    longest_streak: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_activity_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class MediaMixin(TimestampMixin):
    """Campos comuns a toda mídia acompanhada pelo usuário."""

    # Transitório, nunca persistido: o router preenche em create/update com as
    # conquistas recém-desbloqueadas, para o app exibir o toast na hora.
    # Tupla vazia como default por ser imutável — evita estado compartilhado
    # entre instâncias.
    unlocked_achievements = ()

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=MediaStatus.PLANO, server_default=MediaStatus.PLANO
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Preenchido quando o status vira "finalizado"; usado pelas conquistas.
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Item do catálogo global que originou este registro. Nullable porque o
    # cadastro manual continua existindo e os itens antigos não têm vínculo.
    @declared_attr
    def media_id(cls) -> Mapped[int | None]:
        return mapped_column(ForeignKey("media_items.id"), nullable=True, index=True)


class Livro(MediaMixin, Base):
    __tablename__ = "livros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    pages_read: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chapters_done: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class Serie(MediaMixin, Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    episodes_watched: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Dorama(MediaMixin, Base):
    """Série asiática. Tabela própria para o usuário separar da estante de séries."""

    __tablename__ = "doramas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    episodes_watched: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Filme(MediaMixin, Base):
    __tablename__ = "filmes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)


class Anime(MediaMixin, Base):
    __tablename__ = "animes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    episodes_watched: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_episodes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Achievement(Base):
    """Conquista desbloqueada por um usuário. O catálogo vive em app/achievements.py."""

    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("user_id", "code", name="uq_achievement_user_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class MediaItem(TimestampMixin, Base):
    """Item de catálogo vindo de uma API externa, cacheado sob demanda.

    Global e compartilhado entre usuários — sem user_id. A avaliação de cada
    um vive nas tabelas por tipo, que apontam para cá via media_id.

    O índice único (source, external_id) é o que impede duplicidade quando dois
    usuários adicionam o mesmo item ao mesmo tempo: o upsert em
    app/media_cache.py depende dele.
    """

    __tablename__ = "media_items"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_media_items_source_external"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # String porque o Google Books usa ID alfanumérico ("zyTCAlFPjgYC"),
    # enquanto TMDB e AniList usam inteiro.
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)
    media_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Só a URL, nunca o binário da imagem.
    poster_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    release_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Quando o dado foi lido da fonte pela última vez. Guia o TTL do cache.
    refreshed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    # Resposta crua da fonte: evita uma rodada de re-fetch quando um campo novo
    # (gênero, duração, autor) entrar na spec. JSONB no Postgres, JSON no SQLite.
    raw_payload: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )


class PendingMediaLink(Base):
    """Vínculo item-do-usuário -> catálogo que falhou na hora de salvar.

    Existe para a falha ao gravar o cache nunca virar erro visível: a avaliação
    do usuário é gravada com media_id nulo e o vínculo é refeito depois, pela
    varredura oportunista de app/media_cache.py.
    """

    __tablename__ = "pending_media_links"
    __table_args__ = (
        UniqueConstraint("route_type", "item_id", name="uq_pending_media_links_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Plural, como nas rotas ("animes"): identifica a tabela do item do usuário.
    route_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)

    source: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(64), nullable=False)

    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
