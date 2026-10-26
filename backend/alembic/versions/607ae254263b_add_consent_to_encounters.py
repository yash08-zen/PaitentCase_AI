"""add_consent_to_encounters

Revision ID: 607ae254263b
Revises: 1cc939388310
Create Date: 2026-10-23 12:26:17.186851

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '607ae254263b'
down_revision: Union[str, None] = '1cc939388310'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('encounters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('consent_given', sa.Boolean(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('consent_timestamp', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('encounters', schema=None) as batch_op:
        batch_op.drop_column('consent_timestamp')
        batch_op.drop_column('consent_given')
