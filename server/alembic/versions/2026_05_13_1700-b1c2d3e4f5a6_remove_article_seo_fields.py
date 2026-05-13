"""remove article seo fields

Revision ID: b1c2d3e4f5a6
Revises: 7f8a9b0c1d2e
Create Date: 2026-05-13 17:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "7f8a9b0c1d2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_article_details_seo_title_length", "article_details", type_="check")
    op.drop_constraint("ck_article_details_seo_description_length", "article_details", type_="check")
    op.drop_column("article_details", "seo_title")
    op.drop_column("article_details", "seo_description")


def downgrade() -> None:
    op.add_column("article_details", sa.Column("seo_title", sa.String(length=300), nullable=True))
    op.add_column("article_details", sa.Column("seo_description", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_article_details_seo_title_length",
        "article_details",
        "char_length(seo_title) <= 300",
    )
    op.create_check_constraint(
        "ck_article_details_seo_description_length",
        "article_details",
        "seo_description IS NULL OR char_length(seo_description) <= 320",
    )

