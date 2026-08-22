"""multi_tenancy_esikler_kurallar

Revision ID: e5a8d7901234
Revises: 47ab31706e6f
Create Date: 2026-08-17 17:40:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a8d7901234'
down_revision: Union[str, Sequence[str], None] = '47ab31706e6f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add multi-tenancy organization_id to esik_degerleri and anomali_kurallari."""
    # 1. Add organization_id column as NULLABLE first
    op.add_column('esik_degerleri', sa.Column('organization_id', sa.Uuid(), nullable=True))
    op.add_column('anomali_kurallari', sa.Column('organization_id', sa.Uuid(), nullable=True))

    # 2. Backfill existing records with the existing default organization ID
    default_org_id = uuid.uuid4()
    op.execute(f"""
        DO $$
        DECLARE
            default_org uuid;
        BEGIN
            SELECT id INTO default_org FROM organizations ORDER BY created_at ASC LIMIT 1;
            IF default_org IS NULL THEN
                INSERT INTO organizations (id, name, created_at) VALUES ('{default_org_id}', 'Default Organization', NOW()) RETURNING id INTO default_org;
            END IF;
            UPDATE esik_degerleri SET organization_id = default_org WHERE organization_id IS NULL;
            UPDATE anomali_kurallari SET organization_id = default_org WHERE organization_id IS NULL;
        END $$;
    """)

    # 3. Alter columns to be NOT NULL
    op.alter_column('esik_degerleri', 'organization_id', nullable=False)
    op.alter_column('anomali_kurallari', 'organization_id', nullable=False)

    # 4. Create Foreign Keys
    op.create_foreign_key('fk_esik_degerleri_org', 'esik_degerleri', 'organizations', ['organization_id'], ['id'])
    op.create_foreign_key('fk_anomali_kurallari_org', 'anomali_kurallari', 'organizations', ['organization_id'], ['id'])

    # 5. Replace global unique constraint on parametre_adi with per-organization unique constraint
    op.execute("ALTER TABLE esik_degerleri DROP CONSTRAINT IF EXISTS esik_degerleri_parametre_adi_key;")
    op.create_unique_constraint('uq_esik_org_param', 'esik_degerleri', ['organization_id', 'parametre_adi'])


def downgrade() -> None:
    """Downgrade schema - Remove multi-tenancy from esik_degerleri and anomali_kurallari."""
    op.drop_constraint('uq_esik_org_param', 'esik_degerleri', type_='unique')
    op.create_unique_constraint('esik_degerleri_parametre_adi_key', 'esik_degerleri', ['parametre_adi'])
    op.drop_constraint('fk_anomali_kurallari_org', 'anomali_kurallari', type_='foreignkey')
    op.drop_constraint('fk_esik_degerleri_org', 'esik_degerleri', type_='foreignkey')
    op.drop_column('anomali_kurallari', 'organization_id')
    op.drop_column('esik_degerleri', 'organization_id')
