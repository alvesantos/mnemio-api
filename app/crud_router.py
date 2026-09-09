from typing import Type

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import media_cache, models
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


def _attach_media_ref(
    db: Session,
    item,
    media_ref: dict,
    *,
    route_type: str,
    user_id: int,
) -> bool:
    """Liga o item do usuário ao catálogo. Devolve True se ficou pendente.

    Cache HIT (o caso comum, porque abrir o detalhe já grava o item) resolve na
    hora. MISS não bloqueia o cadastro: a nota do usuário é o dado importante,
    o metadado do catálogo é recuperável — o vínculo vai para a outbox e é
    refeito em background.
    """
    cached = media_cache.get_cached(db, media_ref["source"], media_ref["external_id"])
    if cached is not None:
        item.media_id = cached.id
        return False

    media_cache.enqueue_pending_link(
        db,
        user_id=user_id,
        route_type=route_type,
        item_id=item.id,
        source=media_ref["source"],
        external_id=media_ref["external_id"],
    )
    return True


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
    # "animes", "livros"... — identifica a tabela na outbox de vínculos.
    route_type = prefix.strip("/")

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
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        data = payload.model_dump()
        # media_ref não é coluna: vira media_id depois que o item tem id.
        media_ref = data.pop("media_ref", None)

        item = model(**data, user_id=current_user.id)
        apply_media_rules(item)
        db.add(item)
        # Faz flush, então item.id já existe daqui para baixo.
        unlocked = _register_activity(db, current_user)

        pending = False
        if media_ref:
            pending = _attach_media_ref(
                db, item, media_ref, route_type=route_type, user_id=current_user.id
            )

        db.commit()
        db.refresh(item)
        item.unlocked_achievements = unlocked

        if pending:
            background_tasks.add_task(media_cache.sweep_pending_links, current_user.id)

        return item

    @router.get("/", response_model=list[out_schema])
    def list_items(
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: models.User = Depends(get_current_user),
    ):
        # Varredura oportunista: sem broker, é a próxima request do usuário que
        # reprocessa os vínculos que falharam. Roda depois da resposta.
        background_tasks.add_task(media_cache.sweep_pending_links, current_user.id)
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
