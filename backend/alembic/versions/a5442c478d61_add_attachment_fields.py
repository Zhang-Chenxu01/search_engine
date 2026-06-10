"""add_attachment_fields

Revision ID: a5442c478d61
Revises: 0001
Create Date: 2026-06-10 17:17:34.354726
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a5442c478d61'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attachments', sa.Column('file_size', sa.BigInteger(), nullable=True))
    op.add_column('attachments', sa.Column('parent_title', sa.String(length=512), server_default="", nullable=False))
    op.add_column('attachments', sa.Column('source_site', sa.String(length=64), server_default="", nullable=False))
    op.add_column('attachments', sa.Column('category', sa.String(length=32), server_default="", nullable=False))
    op.add_column('attachments', sa.Column('parse_error', sa.String(length=1024), nullable=True))
    op.add_column('attachments', sa.Column('text_length', sa.Integer(), server_default="0", nullable=False))
    op.add_column('attachments', sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True))


def downgrade() -> None:
    op.drop_column('attachments', 'updated_at')
    op.drop_column('attachments', 'text_length')
    op.drop_column('attachments', 'parse_error')
    op.drop_column('attachments', 'category')
    op.drop_column('attachments', 'source_site')
    op.drop_column('attachments', 'parent_title')
    op.drop_column('attachments', 'file_size')
