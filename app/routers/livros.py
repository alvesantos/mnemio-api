from app import models, schemas
from app.crud_router import make_crud_router

router = make_crud_router(
    prefix="/livros",
    tags=["livros"],
    model=models.Livro,
    create_schema=schemas.LivroCreate,
    update_schema=schemas.LivroUpdate,
    out_schema=schemas.LivroOut,
)
