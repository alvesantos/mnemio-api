"""create media_items and pending_media_links

Revision ID: c1a7d5e9b430
Revises: b2f4a9c17d30
Create Date: 2026-09-09

Catálogo global de mídias cacheado sob demanda. O índice único
(source, external_id) é o que garante idempotência do upsert quando dois
usuários adicionam o mesmo item ao mesmo tempo.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = 'c1a7d5e9b430'
down_revision: Union[str, Sequence[str], None] = 'b2f4a9c17d30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == 'postgresql'

    op.create_table(
        'media_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=64), nullable=False),
        sa.Column('media_type', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('original_title', sa.String(length=300), nullable=True),
        sa.Column('poster_url', sa.String(length=500), nullable=True),
        sa.Column('release_year', sa.Integer(), nullable=True),
        sa.Column('synopsis', sa.Text(), nullable=True),
        sa.Column('refreshed_at', sa.DateTime(), nullable=False),
        sa.Column(
            'raw_payload',
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'external_id', name='uq_media_items_source_external'),
    )
    op.create_index(op.f('ix_media_items_id'), 'media_items', ['id'], unique=False)
    op.create_index(
        op.f('ix_media_items_media_type'), 'media_items', ['media_type'], unique=False
    )
    op.create_index(
        'ix_media_items_refreshed_at', 'media_items', ['refreshed_at'], unique=False
    )

    if is_postgres:
        # Busca textual local: é o fallback quando a fonte externa está fora.
        op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
        op.execute(
            'CREATE INDEX ix_media_items_title_trgm '
            'ON media_items USING gin (title gin_trgm_ops)'
        )

    op.create_table(
        'pending_media_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('route_type', sa.String(length=20), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=64), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('route_type', 'item_id', name='uq_pending_media_links_item'),
    )
    op.create_index(op.f('ix_pending_media_links_id'), 'pending_media_links', ['id'], unique=False)
    op.create_index(
        op.f('ix_pending_media_links_user_id'), 'pending_media_links', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_pending_media_links_user_id'), table_name='pending_media_links')
    op.drop_index(op.f('ix_pending_media_links_id'), table_name='pending_media_links')
    op.drop_table('pending_media_links')

    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP INDEX IF EXISTS ix_media_items_title_trgm')

    op.drop_index('ix_media_items_refreshed_at', table_name='media_items')
    op.drop_index(op.f('ix_media_items_media_type'), table_name='media_items')
    op.drop_index(op.f('ix_media_items_id'), table_name='media_items')
    op.drop_table('media_items')
