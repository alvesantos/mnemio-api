"""Estatísticas agregadas do usuário e contagem de dias consecutivos."""

from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.models import MediaStatus

# Cada modelo com a chave usada nas respostas da API.
MEDIA_MODELS = {
    "livros": models.Livro,
    "series": models.Serie,
    "filmes": models.Filme,
    "animes": models.Anime,
    "doramas": models.Dorama,
}


def touch_activity(user: models.User, today: date | None = None) -> None:
    """Registra atividade de hoje e atualiza a sequência de dias.

    Idempotente dentro do mesmo dia: várias ações não inflam o streak.
    Um dia pulado zera a contagem e recomeça em 1.
    """
    today = today or date.today()
    last = user.last_activity_date

    if last == today:
        return

    if last == today - timedelta(days=1):
        user.streak_count += 1
    else:
        user.streak_count = 1

    user.last_activity_date = today
    user.longest_streak = max(user.longest_streak or 0, user.streak_count)


# Campo de progresso e rótulo por tipo. Filmes não têm progresso numérico.
PROGRESS_BY_TYPE = {
    "livros": ("pages_read", "total_pages", "páginas"),
    "series": ("episodes_watched", "total_episodes", "episódios"),
    "animes": ("episodes_watched", "total_episodes", "episódios"),
    "doramas": ("episodes_watched", "total_episodes", "episódios"),
    "filmes": (None, None, None),
}


def continue_items(db: Session, user: models.User, limit: int = 10) -> list[dict]:
    """Itens em andamento das quatro mídias, do mais recente para o mais antigo."""
    collected: list[dict] = []

    for key, model in MEDIA_MODELS.items():
        current_field, total_field, label = PROGRESS_BY_TYPE[key]
        rows = (
            db.query(model)
            .filter(model.user_id == user.id, model.status == MediaStatus.ANDAMENTO)
            .order_by(model.updated_at.desc())
            .limit(limit)
            .all()
        )
        for row in rows:
            collected.append(
                {
                    "id": row.id,
                    "type": key,
                    "title": row.title,
                    "status": row.status,
                    "rating": row.rating,
                    "progress_current": getattr(row, current_field) if current_field else None,
                    "progress_total": getattr(row, total_field) if total_field else None,
                    "progress_label": label,
                    "updated_at": row.updated_at,
                }
            )

    collected.sort(key=lambda item: item["updated_at"], reverse=True)
    return collected[:limit]


def _count(db: Session, model, user_id: int, *conditions) -> int:
    query = db.query(func.count(model.id)).filter(model.user_id == user_id)
    for condition in conditions:
        query = query.filter(condition)
    return query.scalar() or 0


def compute_user_stats(db: Session, user: models.User) -> dict:
    """Números usados pelo perfil e pela avaliação das conquistas."""
    finished_by_type: dict[str, int] = {}
    totals = {"total": 0, "finished": 0, "in_progress": 0, "dropped": 0, "rated": 0, "noted": 0}

    for key, model in MEDIA_MODELS.items():
        finished_by_type[key] = _count(
            db, model, user.id, model.status == MediaStatus.FINALIZADO
        )
        totals["total"] += _count(db, model, user.id)
        totals["in_progress"] += _count(
            db, model, user.id, model.status == MediaStatus.ANDAMENTO
        )
        totals["dropped"] += _count(db, model, user.id, model.status == MediaStatus.DROPADO)
        totals["rated"] += _count(db, model, user.id, model.rating.isnot(None))
        totals["noted"] += _count(db, model, user.id, model.notes.isnot(None), model.notes != "")

    totals["finished"] = sum(finished_by_type.values())

    return {
        **totals,
        "finished_by_type": finished_by_type,
        "streak_count": user.streak_count or 0,
        "longest_streak": user.longest_streak or 0,
    }
