"""create article_embedding_index

Revision ID: 0001
Revises:
Create Date: 2026-02-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.create_table(
        'article_embedding_index',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'article_revision_id',
            sa.Integer(),
            sa.ForeignKey('article_revision.id', ondelete='CASCADE'),
            nullable=False,
            unique=True,
        ),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table('article_embedding_index')
