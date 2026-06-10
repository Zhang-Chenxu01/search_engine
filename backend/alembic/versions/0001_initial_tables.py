"""Initial tables — pages, attachments, page_links, users, query_logs, click_logs

Revision ID: 0001
Revises:
Create Date: 2026-06-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("normalized_url", sa.String(767), nullable=False),
        sa.Column("title", sa.String(512), nullable=False, server_default=""),
        sa.Column("source_site", sa.String(64), nullable=False, server_default=""),
        sa.Column("category", sa.String(32), nullable=False, server_default=""),
        sa.Column("publish_time", sa.DateTime(), nullable=True),
        sa.Column("crawl_time", sa.DateTime(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("snapshot_path", sa.String(512), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("es_doc_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_url"),
    )
    op.create_index("idx_pages_normalized_url", "pages", ["normalized_url"])
    op.create_index("idx_pages_source_site", "pages", ["source_site"])
    op.create_index("idx_pages_category", "pages", ["category"])
    op.create_index("idx_pages_publish_time", "pages", ["publish_time"])
    op.create_index("idx_pages_crawl_time", "pages", ["crawl_time"])
    op.create_index("idx_pages_content_hash", "pages", ["content_hash"])
    op.create_index("idx_pages_status_code", "pages", ["status_code"])

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="user"),
        sa.Column("college", sa.String(128), nullable=False, server_default=""),
        sa.Column("interests", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_role", "users", ["role"])
    op.create_index("idx_users_college", "users", ["college"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_url", sa.String(2048), nullable=False),
        sa.Column("normalized_file_url", sa.String(767), nullable=False),
        sa.Column("file_name", sa.String(512), nullable=False, server_default=""),
        sa.Column("file_type", sa.String(32), nullable=False, server_default=""),
        sa.Column("local_path", sa.String(1024), nullable=True),
        sa.Column("parent_page_id", sa.BigInteger(), nullable=True),
        sa.Column("parent_url", sa.String(2048), nullable=False, server_default=""),
        sa.Column("content_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("parse_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("es_doc_id", sa.String(64), nullable=True),
        sa.Column("crawl_time", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_page_id"], ["pages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_file_url"),
    )
    op.create_index("idx_attachments_norm_url", "attachments", ["normalized_file_url"])
    op.create_index("idx_attachments_parent_page", "attachments", ["parent_page_id"])
    op.create_index("idx_attachments_file_type", "attachments", ["file_type"])
    op.create_index("idx_attachments_parse_status", "attachments", ["parse_status"])
    op.create_index("idx_attachments_crawl_time", "attachments", ["crawl_time"])
    op.create_index("idx_attachments_content_hash", "attachments", ["content_hash"])

    op.create_table(
        "page_links",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("from_url", sa.String(2048), nullable=False),
        sa.Column("to_url", sa.String(2048), nullable=False),
        sa.Column("anchor_text", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_page_links_from_url", "page_links", ["from_url"], mysql_length={"from_url": 767})
    op.create_index("idx_page_links_to_url", "page_links", ["to_url"], mysql_length={"to_url": 767})

    op.create_table(
        "query_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("query_text", sa.String(512), nullable=False),
        sa.Column("query_type", sa.String(32), nullable=False, server_default="fulltext"),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_query_logs_user_id", "query_logs", ["user_id"])
    op.create_index("idx_query_logs_query_text", "query_logs", ["query_text"])
    op.create_index("idx_query_logs_created_at", "query_logs", ["created_at"])

    op.create_table(
        "click_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("query_log_id", sa.BigInteger(), nullable=True),
        sa.Column("target_type", sa.String(32), nullable=False, server_default="page"),
        sa.Column("target_url", sa.String(2048), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_click_logs_user_id", "click_logs", ["user_id"])
    op.create_index("idx_click_logs_query_log_id", "click_logs", ["query_log_id"])
    op.create_index("idx_click_logs_target_type", "click_logs", ["target_type"])
    op.create_index("idx_click_logs_target_url", "click_logs", ["target_url"], mysql_length={"target_url": 767})
    op.create_index("idx_click_logs_created_at", "click_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("click_logs")
    op.drop_table("query_logs")
    op.drop_table("page_links")
    op.drop_table("attachments")
    op.drop_table("users")
    op.drop_table("pages")
