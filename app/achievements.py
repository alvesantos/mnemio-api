"""Catálogo de conquistas e a lógica que as desbloqueia.

O catálogo vive em código (não no banco) para poder crescer sem migration.
A tabela `achievements` guarda apenas o que cada usuário já desbloqueou.
"""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app import models


@dataclass(frozen=True)
class AchievementDef:
    code: str
    title: str
    description: str
    icon: str  # nome de ícone Ionicons, usado pelo app
    # Recebe o dicionário de app.stats.compute_user_stats.
    condition: Callable[[dict], bool]
    # Progresso atual e alvo, para a barra no perfil.
    progress: Callable[[dict], int]
    target: int


CATALOG: tuple[AchievementDef, ...] = (
    AchievementDef(
        code="primeira_vez",
        title="A primeira vez a gente nunca esquece",
        description="Finalize sua primeira obra.",
        icon="sparkles",
        condition=lambda s: s["finished"] >= 1,
        progress=lambda s: s["finished"],
        target=1,
    ),
    AchievementDef(
        code="leitor_nato",
        title="Leitor Nato",
        description="Finalize 10 livros.",
        icon="book",
        condition=lambda s: s["finished_by_type"]["livros"] >= 10,
        progress=lambda s: s["finished_by_type"]["livros"],
        target=10,
    ),
    AchievementDef(
        code="maratonista",
        title="Maratonista",
        description="Finalize 10 séries.",
        icon="tv",
        condition=lambda s: s["finished_by_type"]["series"] >= 10,
        progress=lambda s: s["finished_by_type"]["series"],
        target=10,
    ),
    AchievementDef(
        code="cinefilo",
        title="Cinéfilo",
        description="Finalize 10 filmes.",
        icon="film",
        condition=lambda s: s["finished_by_type"]["filmes"] >= 10,
        progress=lambda s: s["finished_by_type"]["filmes"],
        target=10,
    ),
    AchievementDef(
        code="otaku",
        title="Otaku",
        description="Finalize 10 animes.",
        icon="flash",
        condition=lambda s: s["finished_by_type"]["animes"] >= 10,
        progress=lambda s: s["finished_by_type"]["animes"],
        target=10,
    ),
    AchievementDef(
        code="dorameiro",
        title="Dorameiro",
        description="Finalize 10 doramas.",
        icon="heart",
        condition=lambda s: s["finished_by_type"]["doramas"] >= 10,
        progress=lambda s: s["finished_by_type"]["doramas"],
        target=10,
    ),
    AchievementDef(
        code="colecionador",
        title="Colecionador",
        description="Tenha 50 obras cadastradas.",
        icon="albums",
        condition=lambda s: s["total"] >= 50,
        progress=lambda s: s["total"],
        target=50,
    ),
    AchievementDef(
        code="centuriao",
        title="Centurião",
        description="Finalize 100 obras.",
        icon="trophy",
        condition=lambda s: s["finished"] >= 100,
        progress=lambda s: s["finished"],
        target=100,
    ),
    AchievementDef(
        code="constancia",
        title="Constância",
        description="Mantenha 7 dias seguidos de atividade.",
        icon="flame",
        condition=lambda s: s["longest_streak"] >= 7,
        progress=lambda s: s["longest_streak"],
        target=7,
    ),
    AchievementDef(
        code="inabalavel",
        title="Inabalável",
        description="Mantenha 30 dias seguidos de atividade.",
        icon="bonfire",
        condition=lambda s: s["longest_streak"] >= 30,
        progress=lambda s: s["longest_streak"],
        target=30,
    ),
    AchievementDef(
        code="critico",
        title="Crítico",
        description="Avalie 10 obras.",
        icon="star",
        condition=lambda s: s["rated"] >= 10,
        progress=lambda s: s["rated"],
        target=10,
    ),
    AchievementDef(
        code="resenhista",
        title="Resenhista",
        description="Escreva anotações em 10 obras.",
        icon="create",
        condition=lambda s: s["noted"] >= 10,
        progress=lambda s: s["noted"],
        target=10,
    ),
    AchievementDef(
        code="sem_medo_de_largar",
        title="Sem Medo de Largar",
        description="Abandone 5 obras. A vida é curta.",
        icon="exit",
        condition=lambda s: s["dropped"] >= 5,
        progress=lambda s: s["dropped"],
        target=5,
    ),
)

BY_CODE = {definition.code: definition for definition in CATALOG}


def unlocked_codes(db: Session, user_id: int) -> set[str]:
    rows = db.query(models.Achievement.code).filter(models.Achievement.user_id == user_id).all()
    return {row[0] for row in rows}


def sync_achievements(db: Session, user: models.User, stats: dict) -> list[AchievementDef]:
    """Desbloqueia o que as estatísticas já permitem. Devolve só as novidades.

    Não faz commit: quem chama decide quando persistir.
    """
    already = unlocked_codes(db, user.id)
    newly: list[AchievementDef] = []

    for definition in CATALOG:
        if definition.code in already:
            continue
        if definition.condition(stats):
            db.add(models.Achievement(user_id=user.id, code=definition.code))
            newly.append(definition)

    return newly


def serialize(definition: AchievementDef, stats: dict, unlocked: bool) -> dict:
    return {
        "code": definition.code,
        "title": definition.title,
        "description": definition.description,
        "icon": definition.icon,
        "target": definition.target,
        "progress": min(definition.progress(stats), definition.target),
        "unlocked": unlocked,
    }
