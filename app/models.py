from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


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
