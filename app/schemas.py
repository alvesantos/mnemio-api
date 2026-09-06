from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

MediaStatusLiteral = Literal["plano", "andamento", "finalizado", "dropado"]

NOTES_MAX = 5000


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime
    streak_count: int
    longest_streak: int

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --------------------------------------------------------------------------
# Bases compartilhadas pelas quatro mídias.
# Create exige título; Update deixa tudo opcional (PUT parcial via
# exclude_unset); Out devolve o estado completo.
# --------------------------------------------------------------------------


class MediaCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    rating: float | None = Field(default=None, ge=0, le=5)
    status: MediaStatusLiteral = "plano"
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class MediaUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    rating: float | None = Field(default=None, ge=0, le=5)
    status: MediaStatusLiteral | None = None
    notes: str | None = Field(default=None, max_length=NOTES_MAX)


class MediaOut(BaseModel):
    id: int
    title: str
    rating: float | None
    status: MediaStatusLiteral
    notes: str | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------------
# Livros — progresso em páginas e capítulos
# --------------------------------------------------------------------------


class LivroCreate(MediaCreate):
    pages_read: int = Field(default=0, ge=0)
    total_pages: int | None = Field(default=None, ge=1)
    chapters_done: int = Field(default=0, ge=0)


class LivroUpdate(MediaUpdate):
    pages_read: int | None = Field(default=None, ge=0)
    total_pages: int | None = Field(default=None, ge=1)
    chapters_done: int | None = Field(default=None, ge=0)


class LivroOut(MediaOut):
    pages_read: int
    total_pages: int | None
    chapters_done: int


# --------------------------------------------------------------------------
# Séries e animes — progresso em episódios
# --------------------------------------------------------------------------


class EpisodicCreate(MediaCreate):
    episodes_watched: int = Field(default=0, ge=0)
    total_episodes: int | None = Field(default=None, ge=1)


class EpisodicUpdate(MediaUpdate):
    episodes_watched: int | None = Field(default=None, ge=0)
    total_episodes: int | None = Field(default=None, ge=1)


class EpisodicOut(MediaOut):
    episodes_watched: int
    total_episodes: int | None


class SerieCreate(EpisodicCreate):
    pass


class SerieUpdate(EpisodicUpdate):
    pass


class SerieOut(EpisodicOut):
    pass


class AnimeCreate(EpisodicCreate):
    pass


class AnimeUpdate(EpisodicUpdate):
    pass


class AnimeOut(EpisodicOut):
    pass


# --------------------------------------------------------------------------
# Filmes — sem progresso numérico, só status
# --------------------------------------------------------------------------


class FilmeCreate(MediaCreate):
    pass


class FilmeUpdate(MediaUpdate):
    pass


class FilmeOut(MediaOut):
    pass
