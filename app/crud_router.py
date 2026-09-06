from typing import Type

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.achievements import serialize, sync_achievements
from app.database import get_db
from app.deps import get_current_user
from app.media_rules import apply_media_rules
from app.stats import compute_user_stats, touch_activity


def _register_activity(db: Session, current_user: models.User) -> list[dict]:
    """Atualiza streak e desbloqueia conquistas após uma mudança.

    O flush é necessário para que o item recém-salvo já entre nas contagens
    de compute_user_stats, que consulta o banco.
    """
    touch_activity(current_user)
    db.flush()
    stats = compute_user_stats(db, current_user)
    newly = sync_achievements(db, current_user, stats)
    return [serialize(definition, stats, unlocked=True) for definition in newly]


def make_crud_router(
    *,
    prefix: str,
    tags: list[str],
    model: type,
    create_schema: Type[BaseModel],
    update_schema: Type[BaseModel],
    out_schema: Type[BaseModel],
) -> APIRouter:
    """Builds a CRUD router for a user-owned resource (create/list/get/update/delete)."""

    router = APIRouter(prefix=prefix, tags=tags)

    def _get_owned_or_404(item_id: int, db: Session, current_user: models.User):
        item = (
            db.query(model)
            .filter(model.id == item_id, model.user_id == current_user.id)
            .first()
        )
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return item

    @router.post("/", response_model=out_schema, status_code=status.HTTP_201_CREATED)
    def create_item(
        payload: create_schema,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        item = model(**payload.model_dump(), user_id=current_user.id)
        apply_media_rules(item)
        db.add(item)
        unlocked = _register_activity(db, current_user)
        db.commit()
        db.refresh(item)
        item.unlocked_achievements = unlocked
        return item

    @router.get("/", response_model=list[out_schema])
    def list_items(
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        return (
            db.query(model)
            .filter(model.user_id == current_user.id)
            .order_by(model.id)
            .all()
        )

    @router.get("/{item_id}", response_model=out_schema)
    def get_item(
        item_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        return _get_owned_or_404(item_id, db, current_user)

    @router.put("/{item_id}", response_model=out_schema)
    def update_item(
        item_id: int,
        payload: update_schema,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        item = _get_owned_or_404(item_id, db, current_user)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
        apply_media_rules(item)
        unlocked = _register_activity(db, current_user)
        db.commit()
        db.refresh(item)
        item.unlocked_achievements = unlocked
        return item

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_item(
        item_id: int,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        item = _get_owned_or_404(item_id, db, current_user)
        db.delete(item)
        db.commit()

    return router
