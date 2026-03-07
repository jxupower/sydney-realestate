"""Add named unique constraints for ON CONFLICT upserts.

Revision ID: 0002
Revises: 0001
Create Date: 2025-03-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ml_valuations: add named unique constraint on (property_id, model_version)
    # so ON CONFLICT upserts can reference it by name.
    op.create_unique_constraint(
        "uq_valuation_property_version",
        "ml_valuations",
        ["property_id", "model_version"],
    )

    # osm_amenities: add a named unique constraint on suburb_id
    # (the column-level unique=True in 0001 creates an auto-named constraint;
    # we add this named one so code can reference it explicitly).
    op.create_unique_constraint("uq_osm_suburb", "osm_amenities", ["suburb_id"])


def downgrade() -> None:
    op.drop_constraint("uq_osm_suburb", "osm_amenities", type_="unique")
    op.drop_constraint("uq_valuation_property_version", "ml_valuations", type_="unique")
