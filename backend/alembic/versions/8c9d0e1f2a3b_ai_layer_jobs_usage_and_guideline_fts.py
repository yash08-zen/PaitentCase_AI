"""ai_layer_jobs_usage_and_guideline_fts

Adds LLM job usage/notes columns, the DocumentEntity review flag, and the
SQLite FTS5 index used for guideline passage retrieval.

Revision ID: 8c9d0e1f2a3b
Revises: 7a8b9c0d1e2f
Create Date: 2026-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c9d0e1f2a3b'
down_revision: Union[str, None] = '7a8b9c0d1e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('llm_jobs') as batch:
        batch.add_column(sa.Column('usage', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('notes', sa.JSON(), nullable=True))
    with op.batch_alter_table('document_entities') as batch:
        batch.add_column(sa.Column('review_status', sa.String(length=50), nullable=True))
    op.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS guideline_passages_fts "
        "USING fts5(passage_id UNINDEXED, topic, section, passage_text)"
    )
    op.execute(
        "INSERT INTO guideline_passages_fts (passage_id, topic, section, passage_text) "
        "SELECT id, condition_or_topic, section, passage_text FROM guideline_passages"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS guideline_passages_fts")
    with op.batch_alter_table('document_entities') as batch:
        batch.drop_column('review_status')
    with op.batch_alter_table('llm_jobs') as batch:
        batch.drop_column('notes')
        batch.drop_column('usage')
