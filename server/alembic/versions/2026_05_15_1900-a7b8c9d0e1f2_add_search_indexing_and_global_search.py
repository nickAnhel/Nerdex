"""add search indexing and global search

Revision ID: a7b8c9d0e1f2
Revises: d3e4f5a6b7c8
Create Date: 2026-05-15 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.add_column(
        "content",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            nullable=False,
            server_default=sa.text("''::tsvector"),
        ),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION build_content_search_vector(target_content_id uuid)
        RETURNS tsvector
        LANGUAGE sql
        STABLE
        AS $$
        SELECT to_tsvector(
            'simple',
            trim(
                both ' '
                from concat_ws(
                    ' ',
                    coalesce(c.title, ''),
                    coalesce(c.excerpt, ''),
                    coalesce(pd.body_text, ''),
                    coalesce(ad.body_markdown, ''),
                    coalesce(vd.description, ''),
                    coalesce(md.caption, ''),
                    coalesce(tags_data.tags_text, '')
                )
            )
        )
        FROM content c
        LEFT JOIN post_details pd ON pd.content_id = c.content_id
        LEFT JOIN article_details ad ON ad.content_id = c.content_id
        LEFT JOIN video_details vd ON vd.content_id = c.content_id
        LEFT JOIN moment_details md ON md.content_id = c.content_id
        LEFT JOIN LATERAL (
            SELECT string_agg(t.slug, ' ') AS tags_text
            FROM content_tags ct
            JOIN tags t ON t.tag_id = ct.tag_id
            WHERE ct.content_id = c.content_id
        ) AS tags_data ON true
        WHERE c.content_id = target_content_id
        $$
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_content_search_vector()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_id uuid;
        BEGIN
            target_id := COALESCE(NEW.content_id, OLD.content_id);

            UPDATE content
            SET search_vector = build_content_search_vector(target_id)
            WHERE content_id = target_id;

            RETURN NULL;
        END;
        $$
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_content_search_vector_for_content_tags()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP IN ('UPDATE', 'DELETE') THEN
                UPDATE content
                SET search_vector = build_content_search_vector(OLD.content_id)
                WHERE content_id = OLD.content_id;
            END IF;

            IF TG_OP IN ('INSERT', 'UPDATE') THEN
                UPDATE content
                SET search_vector = build_content_search_vector(NEW.content_id)
                WHERE content_id = NEW.content_id;
            END IF;

            RETURN NULL;
        END;
        $$
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_content_search_vector_for_tags()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            target_tag_id uuid;
        BEGIN
            target_tag_id := COALESCE(NEW.tag_id, OLD.tag_id);

            UPDATE content
            SET search_vector = build_content_search_vector(content.content_id)
            WHERE content.content_id IN (
                SELECT ct.content_id
                FROM content_tags ct
                WHERE ct.tag_id = target_tag_id
            );

            RETURN NULL;
        END;
        $$
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_content_search_vector_refresh
        AFTER INSERT OR UPDATE OF title, excerpt ON content
        FOR EACH ROW
        EXECUTE FUNCTION refresh_content_search_vector()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_post_details_search_vector_refresh
        AFTER INSERT OR UPDATE OF body_text ON post_details
        FOR EACH ROW
        EXECUTE FUNCTION refresh_content_search_vector()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_article_details_search_vector_refresh
        AFTER INSERT OR UPDATE OF body_markdown ON article_details
        FOR EACH ROW
        EXECUTE FUNCTION refresh_content_search_vector()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_video_details_search_vector_refresh
        AFTER INSERT OR UPDATE OF description ON video_details
        FOR EACH ROW
        EXECUTE FUNCTION refresh_content_search_vector()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_moment_details_search_vector_refresh
        AFTER INSERT OR UPDATE OF caption ON moment_details
        FOR EACH ROW
        EXECUTE FUNCTION refresh_content_search_vector()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_content_tags_search_vector_refresh
        AFTER INSERT OR UPDATE OR DELETE ON content_tags
        FOR EACH ROW
        EXECUTE FUNCTION refresh_content_search_vector_for_content_tags()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_tags_search_vector_refresh
        AFTER UPDATE OF slug OR DELETE ON tags
        FOR EACH ROW
        EXECUTE FUNCTION refresh_content_search_vector_for_tags()
        """
    )

    op.execute("UPDATE content SET search_vector = build_content_search_vector(content_id)")

    op.create_index("ix_content_search_vector", "content", [sa.text("search_vector")], postgresql_using="gin")
    op.execute("CREATE INDEX ix_content_title_trgm ON content USING gin (coalesce(title, '') gin_trgm_ops)")
    op.execute("CREATE INDEX ix_content_excerpt_trgm ON content USING gin (coalesce(excerpt, '') gin_trgm_ops)")

    op.create_index(
        "ix_users_search_vector",
        "users",
        [sa.text("to_tsvector('simple', coalesce(username, '') || ' ' || coalesce(display_name, '') || ' ' || coalesce(bio, ''))")],
        postgresql_using="gin",
    )
    op.execute("CREATE INDEX ix_users_display_name_trgm ON users USING gin (coalesce(display_name, '') gin_trgm_ops)")
    op.create_index("ix_users_created_at", "users", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_users_created_at", table_name="users")
    op.execute("DROP INDEX IF EXISTS ix_users_display_name_trgm")
    op.drop_index("ix_users_search_vector", table_name="users")

    op.execute("DROP INDEX IF EXISTS ix_content_excerpt_trgm")
    op.execute("DROP INDEX IF EXISTS ix_content_title_trgm")
    op.drop_index("ix_content_search_vector", table_name="content")

    op.execute("DROP TRIGGER IF EXISTS trg_tags_search_vector_refresh ON tags")
    op.execute("DROP TRIGGER IF EXISTS trg_content_tags_search_vector_refresh ON content_tags")
    op.execute("DROP TRIGGER IF EXISTS trg_moment_details_search_vector_refresh ON moment_details")
    op.execute("DROP TRIGGER IF EXISTS trg_video_details_search_vector_refresh ON video_details")
    op.execute("DROP TRIGGER IF EXISTS trg_article_details_search_vector_refresh ON article_details")
    op.execute("DROP TRIGGER IF EXISTS trg_post_details_search_vector_refresh ON post_details")
    op.execute("DROP TRIGGER IF EXISTS trg_content_search_vector_refresh ON content")

    op.execute("DROP FUNCTION IF EXISTS refresh_content_search_vector_for_tags()")
    op.execute("DROP FUNCTION IF EXISTS refresh_content_search_vector_for_content_tags()")
    op.execute("DROP FUNCTION IF EXISTS refresh_content_search_vector()")
    op.execute("DROP FUNCTION IF EXISTS build_content_search_vector(uuid)")

    op.drop_column("content", "search_vector")
    op.drop_column("users", "created_at")
