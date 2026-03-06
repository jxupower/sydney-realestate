"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-03-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- suburbs ---
    op.create_table(
        "suburbs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("postcode", sa.String(4), nullable=False),
        sa.Column("lga", sa.String(100)),
        sa.Column("state", sa.String(3), server_default="NSW"),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("boundary_geojson", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("name", "postcode", name="uq_suburb_name_postcode"),
    )

    # --- suburb_stats ---
    op.create_table(
        "suburb_stats",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("suburb_id", sa.Integer, nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("median_price", sa.Integer),
        sa.Column("median_price_house", sa.Integer),
        sa.Column("median_price_unit", sa.Integer),
        sa.Column("rental_yield_pct", sa.Float),
        sa.Column("capital_growth_1yr", sa.Float),
        sa.Column("capital_growth_3yr", sa.Float),
        sa.Column("capital_growth_5yr", sa.Float),
        sa.Column("capital_growth_10yr", sa.Float),
        sa.Column("days_on_market_median", sa.SmallInteger),
        sa.Column("clearance_rate_pct", sa.Float),
        sa.Column("total_listings", sa.Integer),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["suburb_id"], ["suburbs.id"]),
        sa.UniqueConstraint("suburb_id", "snapshot_date", name="uq_suburb_stats_date"),
    )
    op.create_index("ix_suburb_stats_suburb_id", "suburb_stats", ["suburb_id"])

    # --- properties ---
    op.create_table(
        "properties",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("url", sa.Text, unique=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="for_sale"),
        sa.Column("property_type", sa.String(30)),
        sa.Column("address_street", sa.String(200)),
        sa.Column("address_suburb", sa.String(100)),
        sa.Column("address_postcode", sa.String(4)),
        sa.Column("suburb_id", sa.Integer),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("land_size_sqm", sa.Float),
        sa.Column("floor_area_sqm", sa.Float),
        sa.Column("bedrooms", sa.SmallInteger),
        sa.Column("bathrooms", sa.SmallInteger),
        sa.Column("car_spaces", sa.SmallInteger),
        sa.Column("year_built", sa.SmallInteger),
        sa.Column("list_price", sa.BigInteger),
        sa.Column("price_guide_low", sa.BigInteger),
        sa.Column("price_guide_high", sa.BigInteger),
        sa.Column("listed_at", sa.DateTime(timezone=True)),
        sa.Column("sold_at", sa.DateTime(timezone=True)),
        sa.Column("sold_price", sa.BigInteger),
        sa.Column("description", sa.Text),
        sa.Column("features", sa.JSON),
        sa.Column("agent_name", sa.String(200)),
        sa.Column("agency_name", sa.String(200)),
        sa.Column("raw_json", sa.JSON),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["suburb_id"], ["suburbs.id"]),
        sa.UniqueConstraint("source", "external_id", name="uq_property_source_external"),
    )
    op.create_index("ix_properties_suburb_id", "properties", ["suburb_id"])
    op.create_index("ix_properties_status", "properties", ["status"])
    op.create_index("ix_properties_listed_at", "properties", ["listed_at"])
    op.create_index("ix_properties_latlong", "properties", ["latitude", "longitude"])

    # --- property_images ---
    op.create_table(
        "property_images",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("property_id", sa.Integer, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("display_order", sa.SmallInteger, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_property_images_property_id", "property_images", ["property_id"])

    # --- valuer_general_records ---
    op.create_table(
        "valuer_general_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("lot_plan", sa.String(50)),
        sa.Column("address_street", sa.String(200)),
        sa.Column("address_suburb", sa.String(100)),
        sa.Column("address_postcode", sa.String(4)),
        sa.Column("lga", sa.String(100)),
        sa.Column("land_value_cents", sa.BigInteger),
        sa.Column("capital_value_cents", sa.BigInteger),
        sa.Column("improvement_value_cents", sa.BigInteger),
        sa.Column("base_date", sa.Date),
        sa.Column("property_id", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"]),
        sa.UniqueConstraint("lot_plan", "base_date", name="uq_vg_lot_plan_date"),
    )
    op.create_index("ix_vg_lot_plan", "valuer_general_records", ["lot_plan"])
    op.create_index("ix_vg_property_id", "valuer_general_records", ["property_id"])

    # --- osm_amenities ---
    op.create_table(
        "osm_amenities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("suburb_id", sa.Integer, unique=True, nullable=False),
        sa.Column("nearest_train_km", sa.Float),
        sa.Column("nearest_bus_stop_km", sa.Float),
        sa.Column("train_stations_2km", sa.Integer),
        sa.Column("bus_stops_500m", sa.Integer),
        sa.Column("primary_schools_2km", sa.Integer),
        sa.Column("secondary_schools_3km", sa.Integer),
        sa.Column("supermarkets_1km", sa.Integer),
        sa.Column("parks_1km", sa.Integer),
        sa.Column("walkability_score", sa.Float),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["suburb_id"], ["suburbs.id"]),
    )

    # --- ml_valuations ---
    op.create_table(
        "ml_valuations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("property_id", sa.Integer, nullable=False),
        sa.Column("model_version", sa.String(50), nullable=False),
        sa.Column("predicted_value_cents", sa.BigInteger),
        sa.Column("confidence_interval_low", sa.BigInteger),
        sa.Column("confidence_interval_high", sa.BigInteger),
        sa.Column("underval_score_pct", sa.Float),
        sa.Column("feature_importances", sa.JSON),
        sa.Column("predicted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_ml_valuations_property_id", "ml_valuations", ["property_id"])
    op.create_index("ix_ml_valuations_score", "ml_valuations", ["underval_score_pct"])

    # --- watchlist ---
    op.create_table(
        "watchlist",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("property_id", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("session_id", "property_id", name="uq_watchlist_session_property"),
    )
    op.create_index("ix_watchlist_session_id", "watchlist", ["session_id"])

    # --- ingestion_runs ---
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("records_fetched", sa.Integer),
        sa.Column("records_inserted", sa.Integer),
        sa.Column("records_updated", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_ingestion_runs_source", "ingestion_runs", ["source"])


def downgrade() -> None:
    op.drop_table("ingestion_runs")
    op.drop_table("watchlist")
    op.drop_table("ml_valuations")
    op.drop_table("osm_amenities")
    op.drop_table("valuer_general_records")
    op.drop_table("property_images")
    op.drop_table("properties")
    op.drop_table("suburb_stats")
    op.drop_table("suburbs")
