from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LivroCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    rating: float | None = Field(default=None, ge=0, le=5)


class LivroUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    rating: float | None = Field(default=None, ge=0, le=5)


class LivroOut(BaseModel):
    id: int
    title: str
    rating: float | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SerieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    rating: float | None = Field(default=None, ge=0, le=5)


class SerieUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    rating: float | None = Field(default=None, ge=0, le=5)


class SerieOut(BaseModel):
    id: int
    title: str
    rating: float | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
