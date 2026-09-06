"""add status, progress, notes, streak and achievements

Revision ID: b2f4a9c17d30
Revises: 81c60621a313
Create Date: 2026-09-06

Colunas NOT NULL entram com server_default para que linhas já existentes
sejam preenchidas sem quebrar a migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = 'b2f4a9c17d30'
down_revision: Union[str, Sequence[str], None] = '81c60621a313'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MEDIA_TABLES = ('livros', 'series', 'filmes', 'animes')
EPISODE_TABLES = ('series', 'animes')


def upgrade() -> None:
    # --- campos comuns a toda mídia ---
    for table in MEDIA_TABLES:
        op.add_column(
            table,
            sa.Column(
                'status',
                sa.String(length=20),
                nullable=False,
                server_default='plano',
            ),
        )
        op.add_column(table, sa.Column('notes', sa.Text(), nullable=True))
        op.add_column(table, sa.Column('finished_at', sa.DateTime(), nullable=True))

    # --- progresso de leitura ---
    op.add_column(
        'livros',
        sa.Column('pages_read', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column('livros', sa.Column('total_pages', sa.Integer(), nullable=True))
    op.add_column(
        'livros',
        sa.Column('chapters_done', sa.Integer(), nullable=False, server_default='0'),
    )

    # --- progresso de episódios ---
    for table in EPISODE_TABLES:
        op.add_column(
            table,
            sa.Column('episodes_watched', sa.Integer(), nullable=False, server_default='0'),
        )
        op.add_column(table, sa.Column('total_episodes', sa.Integer(), nullable=True))

    # --- streak do usuário ---
    op.add_column(
        'users',
        sa.Column('streak_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'users',
        sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column('users', sa.Column('last_activity_date', sa.Date(), nullable=True))

    # --- conquistas desbloqueadas ---
    op.create_table(
        'achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('unlocked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'code', name='uq_achievement_user_code'),
    )
    op.create_index(op.f('ix_achievements_id'), 'achievements', ['id'])
    op.create_index(op.f('ix_achievements_user_id'), 'achievements', ['user_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_achievements_user_id'), table_name='achievements')
    op.drop_index(op.f('ix_achievements_id'), table_name='achievements')
    op.drop_table('achievements')

    op.drop_column('users', 'last_activity_date')
    op.drop_column('users', 'longest_streak')
    op.drop_column('users', 'streak_count')

    for table in EPISODE_TABLES:
        op.drop_column(table, 'total_episodes')
        op.drop_column(table, 'episodes_watched')

    op.drop_column('livros', 'chapters_done')
    op.drop_column('livros', 'total_pages')
    op.drop_column('livros', 'pages_read')

    for table in MEDIA_TABLES:
        op.drop_column(table, 'finished_at')
        op.drop_column(table, 'notes')
        op.drop_column(table, 'status')
