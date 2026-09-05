from app import models, schemas
from app.crud_router import make_crud_router

router = make_crud_router(
    prefix="/animes",
    tags=["animes"],
    model=models.Anime,
    create_schema=schemas.AnimeCreate,
    update_schema=schemas.AnimeUpdate,
    out_schema=schemas.AnimeOut,
)
