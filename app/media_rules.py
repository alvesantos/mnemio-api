"""Regras de negócio compartilhadas por livros, séries, filmes e animes."""

from datetime import datetime, timezone

from app.models import MediaStatus

# Campos de progresso existentes em algum dos modelos de mídia.
# Filmes não têm nenhum; livros e séries/animes têm os seus.
PROGRESS_FIELDS = ("pages_read", "chapters_done", "episodes_watched")


def total_progress(item) -> int:
    """Soma o progresso registrado, ignorando campos que o modelo não tem."""
    return sum(getattr(item, field, 0) or 0 for field in PROGRESS_FIELDS)


def apply_media_rules(item) -> None:
    """Normaliza status e finished_at a partir do progresso informado.

    Chamado após criar ou atualizar uma mídia, antes do commit.

    - Registrar progresso em algo que estava no plano move para "andamento".
    - Entrar em "finalizado" carimba finished_at (usado pelas conquistas).
    - Sair de "finalizado" limpa finished_at, para não contar duas vezes.
    """
    if total_progress(item) > 0 and item.status == MediaStatus.PLANO:
        item.status = MediaStatus.ANDAMENTO

    if item.status == MediaStatus.FINALIZADO:
        if item.finished_at is None:
            item.finished_at = datetime.now(timezone.utc)
    else:
        item.finished_at = None
