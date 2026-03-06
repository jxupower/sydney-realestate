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
    # ml_valuations: replace composite index with named unique constraint
    op.drop_index("ix_ml_valuations_property_model", table_name="ml_valuations")
    op.create_unique_constraint(
        "uq_valuation_property_version",
        "ml_valuations",
        ["property_id", "model_version"],
    )

    # osm_amenities: replace anonymous unique with named unique
    # The original column-level unique=True creates an unnamed constraint;
    # drop it by creating the named one (PostgreSQL allows this via ALTER TABLE).
    op.create_unique_constraint("uq_osm_suburb", "osm_amenities", ["suburb_id"])


def downgrade() -> None:
    op.drop_constraint("uq_osm_suburb", "osm_amenities", type_="unique")
    op.drop_constraint("uq_valuation_property_version", "ml_valuations", type_="unique")
    op.create_index(
        "ix_ml_valuations_property_model",
        "ml_valuations",
        ["property_id", "model_version"],
    )
