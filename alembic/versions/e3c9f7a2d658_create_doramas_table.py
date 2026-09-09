"""create doramas table

Revision ID: e3c9f7a2d658
Revises: d2b8e6f1c547
Create Date: 2026-09-09

Dorama espelha série (progresso em episódios). Não é uma fonte nova: no
catálogo é uma série do TMDB filtrada por país de origem.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = 'e3c9f7a2d658'
down_revision: Union[str, Sequence[str], None] = 'd2b8e6f1c547'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'doramas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='plano'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('episodes_watched', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_episodes', sa.Integer(), nullable=True),
        sa.Column('media_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['media_id'], ['media_items.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_doramas_id'), 'doramas', ['id'], unique=False)
    op.create_index(op.f('ix_doramas_user_id'), 'doramas', ['user_id'], unique=False)
    op.create_index('ix_doramas_media_id', 'doramas', ['media_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_doramas_media_id', table_name='doramas')
    op.drop_index(op.f('ix_doramas_user_id'), table_name='doramas')
    op.drop_index(op.f('ix_doramas_id'), table_name='doramas')
    op.drop_table('doramas')
