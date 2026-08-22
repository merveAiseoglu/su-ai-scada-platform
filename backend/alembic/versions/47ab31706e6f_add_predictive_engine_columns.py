"""add predictive engine columns

Revision ID: 47ab31706e6f
Revises: fa5d990d2561
Create Date: 2026-08-17 10:23:52.607054

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47ab31706e6f'
down_revision: Union[str, Sequence[str], None] = 'fa5d990d2561'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add predictive engine columns to su_olcumleri."""
    op.add_column('su_olcumleri', sa.Column('trend_risk_score', sa.Integer(), nullable=True))
    op.add_column('su_olcumleri', sa.Column('trend_direction', sa.String(), nullable=True))
    op.add_column('su_olcumleri', sa.Column('projected_value', sa.Float(), nullable=True))
    op.add_column('su_olcumleri', sa.Column('projection_message', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema - Remove predictive engine columns from su_olcumleri."""
    op.drop_column('su_olcumleri', 'projection_message')
    op.drop_column('su_olcumleri', 'projected_value')
    op.drop_column('su_olcumleri', 'trend_direction')
    op.drop_column('su_olcumleri', 'trend_risk_score')
