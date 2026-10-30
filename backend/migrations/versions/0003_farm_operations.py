"""Farm, shed, flock placement, and tenant settings tables.

Revision ID: 0003_farm_operations
Revises: 0002_identity_and_audit
"""

# SQL trigger bodies are multiline PostgreSQL source and intentionally exceed the Python line width.
# ruff: noqa: E501

import sqlalchemy as sa
from alembic import op

revision = "0003_farm_operations"
down_revision = "0002_identity_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid_type = sa.Uuid()
    op.create_table(
        "farms",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column(
            "tenant_id", uuid_type, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("location", sa.String(500)),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_farms_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_farms_tenant_name"),
    )
    op.create_index("ix_farms_tenant_name", "farms", ["tenant_id", "name"])
    op.create_table(
        "sheds",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("farm_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("capacity_birds", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_sheds_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "id", "farm_id", name="uq_sheds_tenant_id_farm"),
        sa.UniqueConstraint("tenant_id", "farm_id", "name", name="uq_sheds_farm_name"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "farm_id"],
            ["farms.tenant_id", "farms.id"],
            ondelete="RESTRICT",
            name="fk_sheds_tenant_farm",
        ),
        sa.CheckConstraint(
            "capacity_birds IS NULL OR capacity_birds > 0", name="ck_sheds_capacity_positive"
        ),
    )
    op.create_index("ix_sheds_tenant_farm_name", "sheds", ["tenant_id", "farm_id", "name"])
    op.create_table(
        "flocks",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("farm_id", uuid_type, nullable=False),
        sa.Column("shed_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id", name="uq_flocks_tenant_id_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "farm_id"],
            ["farms.tenant_id", "farms.id"],
            ondelete="RESTRICT",
            name="fk_flocks_tenant_farm",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "shed_id", "farm_id"],
            ["sheds.tenant_id", "sheds.id", "sheds.farm_id"],
            ondelete="RESTRICT",
            name="fk_flocks_tenant_shed_farm",
        ),
        sa.CheckConstraint("status IN ('active', 'closed')", name="ck_flocks_status"),
        sa.CheckConstraint(
            "(status = 'active' AND closed_at IS NULL) OR (status = 'closed' AND closed_at IS NOT NULL)",
            name="ck_flocks_closed_timestamp",
        ),
    )
    op.create_index(
        "uq_flocks_one_active_per_shed",
        "flocks",
        ["tenant_id", "shed_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_index(
        "ix_flocks_tenant_farm_status", "flocks", ["tenant_id", "farm_id", "status", "created_at"]
    )
    op.create_unique_constraint("uq_users_tenant_id_id", "users", ["tenant_id", "id"])
    op.create_table(
        "flock_placements",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("tenant_id", uuid_type, nullable=False),
        sa.Column("flock_id", uuid_type, nullable=False),
        sa.Column("placed_on", sa.Date(), nullable=False),
        sa.Column("bird_count", sa.Integer(), nullable=False),
        sa.Column("chick_source", sa.String(160), nullable=False),
        sa.Column("average_weight_kg", sa.Numeric(12, 3)),
        sa.Column("created_by", uuid_type, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "flock_id"],
            ["flocks.tenant_id", "flocks.id"],
            ondelete="CASCADE",
            name="fk_flock_placements_tenant_flock",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "created_by"],
            ["users.tenant_id", "users.id"],
            ondelete="RESTRICT",
            name="fk_placements_tenant_created_by",
        ),
        sa.CheckConstraint("bird_count > 0", name="ck_flock_placements_birds_positive"),
        sa.CheckConstraint(
            "average_weight_kg IS NULL OR average_weight_kg >= 0",
            name="ck_flock_placements_weight_nonnegative",
        ),
    )
    op.create_index(
        "ix_flock_placements_tenant_flock_date",
        "flock_placements",
        ["tenant_id", "flock_id", "placed_on"],
    )
    op.create_table(
        "tenant_settings",
        sa.Column(
            "tenant_id",
            uuid_type,
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("feed_bag_size_kg", sa.Numeric(8, 3)),
        sa.Column("target_mortality_percent", sa.Numeric(6, 3)),
        sa.Column("target_fcr", sa.Numeric(8, 3)),
        sa.Column("updated_by", uuid_type, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "updated_by"],
            ["users.tenant_id", "users.id"],
            ondelete="RESTRICT",
            name="fk_tenant_settings_tenant_updated_by",
        ),
        sa.CheckConstraint(
            "feed_bag_size_kg IS NULL OR feed_bag_size_kg > 0",
            name="ck_tenant_settings_bag_size_positive",
        ),
        sa.CheckConstraint(
            "target_mortality_percent IS NULL OR (target_mortality_percent >= 0 AND target_mortality_percent <= 100)",
            name="ck_tenant_settings_mortality_percent",
        ),
        sa.CheckConstraint(
            "target_fcr IS NULL OR target_fcr > 0", name="ck_tenant_settings_fcr_positive"
        ),
    )

    # Aggregate capacity and closed-flock rules require cross-row checks; serialize placement writes by locking the shed row.
    op.execute("""
    CREATE FUNCTION enforce_flock_placement_capacity() RETURNS trigger AS $$
    DECLARE v_shed_id uuid; v_capacity integer; v_total bigint; v_status text;
    BEGIN
      SELECT s.id, s.capacity_birds, f.status INTO v_shed_id, v_capacity, v_status
      FROM flocks f JOIN sheds s ON s.tenant_id=f.tenant_id AND s.id=f.shed_id
      WHERE f.tenant_id=NEW.tenant_id AND f.id=NEW.flock_id FOR UPDATE OF s;
      IF v_shed_id IS NULL THEN RAISE EXCEPTION 'flock or shed missing'; END IF;
      IF v_status <> 'active' THEN RAISE EXCEPTION 'closed flock is locked'; END IF;
      SELECT COALESCE(SUM(bird_count), 0) INTO v_total FROM flock_placements
      WHERE tenant_id=NEW.tenant_id AND flock_id=NEW.flock_id AND id <> NEW.id;
      IF v_capacity IS NOT NULL AND v_total + NEW.bird_count > v_capacity THEN
        RAISE EXCEPTION 'placement exceeds shed capacity';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_flock_placement_capacity BEFORE INSERT OR UPDATE ON flock_placements
    FOR EACH ROW EXECUTE FUNCTION enforce_flock_placement_capacity();
    CREATE FUNCTION enforce_shed_capacity_change() RETURNS trigger AS $$
    DECLARE v_total bigint;
    BEGIN
      IF NEW.capacity_birds IS NOT NULL THEN
        SELECT COALESCE(SUM(p.bird_count), 0) INTO v_total FROM flocks f JOIN flock_placements p
          ON p.tenant_id=f.tenant_id AND p.flock_id=f.id
          WHERE f.tenant_id=NEW.tenant_id AND f.shed_id=NEW.id AND f.status='active';
        IF v_total > NEW.capacity_birds THEN RAISE EXCEPTION 'capacity is below active placements'; END IF;
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_shed_capacity_change BEFORE UPDATE OF capacity_birds ON sheds
    FOR EACH ROW EXECUTE FUNCTION enforce_shed_capacity_change();
    CREATE FUNCTION enforce_flock_status_transition() RETURNS trigger AS $$
    BEGIN
      IF OLD.status='closed' AND NEW.status='closed' AND
         (NEW.name IS DISTINCT FROM OLD.name OR NEW.farm_id IS DISTINCT FROM OLD.farm_id OR NEW.shed_id IS DISTINCT FROM OLD.shed_id) THEN
        RAISE EXCEPTION 'closed flock is locked';
      END IF;
      IF OLD.status='closed' AND NEW.status='active' THEN
        IF EXISTS (SELECT 1 FROM flocks f WHERE f.tenant_id=NEW.tenant_id AND f.shed_id=NEW.shed_id AND f.status='active' AND f.id<>NEW.id) THEN
          RAISE EXCEPTION 'shed already has an active flock';
        END IF;
        IF EXISTS (SELECT 1 FROM sheds s WHERE s.tenant_id=NEW.tenant_id AND s.id=NEW.shed_id AND s.capacity_birds IS NOT NULL
          AND s.capacity_birds < (SELECT COALESCE(SUM(bird_count),0) FROM flock_placements p WHERE p.tenant_id=NEW.tenant_id AND p.flock_id=NEW.id)) THEN
          RAISE EXCEPTION 'reopened flock exceeds shed capacity';
        END IF;
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql;
    CREATE TRIGGER trg_flock_status_transition BEFORE UPDATE ON flocks
    FOR EACH ROW EXECUTE FUNCTION enforce_flock_status_transition();
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_flock_status_transition ON flocks; DROP FUNCTION IF EXISTS enforce_flock_status_transition(); DROP TRIGGER IF EXISTS trg_shed_capacity_change ON sheds; DROP FUNCTION IF EXISTS enforce_shed_capacity_change(); DROP TRIGGER IF EXISTS trg_flock_placement_capacity ON flock_placements; DROP FUNCTION IF EXISTS enforce_flock_placement_capacity();"
    )
    op.drop_table("tenant_settings")
    op.drop_index("ix_flock_placements_tenant_flock_date", table_name="flock_placements")
    op.drop_table("flock_placements")
    op.drop_constraint("uq_users_tenant_id_id", "users", type_="unique")
    op.drop_index("ix_flocks_tenant_farm_status", table_name="flocks")
    op.drop_index("uq_flocks_one_active_per_shed", table_name="flocks")
    op.drop_table("flocks")
    op.drop_index("ix_sheds_tenant_farm_name", table_name="sheds")
    op.drop_table("sheds")
    op.drop_index("ix_farms_tenant_name", table_name="farms")
    op.drop_table("farms")
