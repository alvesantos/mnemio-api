from app import models, schemas
from app.crud_router import make_crud_router

router = make_crud_router(
    prefix="/filmes",
    tags=["filmes"],
    model=models.Filme,
    create_schema=schemas.FilmeCreate,
    update_schema=schemas.FilmeUpdate,
    out_schema=schemas.FilmeOut,
)
