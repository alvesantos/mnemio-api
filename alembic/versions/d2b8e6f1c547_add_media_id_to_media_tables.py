"""add media_id to media tables

Revision ID: d2b8e6f1c547
Revises: c1a7d5e9b430
Create Date: 2026-09-09

Coluna nullable de propósito: o cadastro manual continua existindo e os itens
já cadastrados ficam sem vínculo, sem backfill.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = 'd2b8e6f1c547'
down_revision: Union[str, Sequence[str], None] = 'c1a7d5e9b430'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MEDIA_TABLES = ('livros', 'series', 'filmes', 'animes')


def upgrade() -> None:
    for table in MEDIA_TABLES:
        op.add_column(table, sa.Column('media_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            f'fk_{table}_media_id_media_items', table, 'media_items', ['media_id'], ['id']
        )
        op.create_index(f'ix_{table}_media_id', table, ['media_id'], unique=False)


def downgrade() -> None:
    for table in MEDIA_TABLES:
        op.drop_index(f'ix_{table}_media_id', table_name=table)
        op.drop_constraint(f'fk_{table}_media_id_media_items', table, type_='foreignkey')
        op.drop_column(table, 'media_id')
