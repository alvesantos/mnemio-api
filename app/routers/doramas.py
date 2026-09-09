from app import models, schemas
from app.crud_router import make_crud_router

router = make_crud_router(
    prefix="/doramas",
    tags=["doramas"],
    model=models.Dorama,
    create_schema=schemas.DoramaCreate,
    update_schema=schemas.DoramaUpdate,
    out_schema=schemas.DoramaOut,
)
