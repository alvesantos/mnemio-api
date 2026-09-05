from app import models, schemas
from app.crud_router import make_crud_router

router = make_crud_router(
    prefix="/series",
    tags=["series"],
    model=models.Serie,
    create_schema=schemas.SerieCreate,
    update_schema=schemas.SerieUpdate,
    out_schema=schemas.SerieOut,
)
