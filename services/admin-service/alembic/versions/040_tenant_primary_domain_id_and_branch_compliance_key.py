"""tenants.primary_domain_id FK + domains.branch_compliance_key

Wires the branch-form's per-vertical compliance sections to the tenant's
industry vertical:

  * ``domains.branch_compliance_key`` (new, nullable) — for industry-vertical
    domains, the literal branches[] nested key / table name that vertical
    unlocks (e.g. ``entities_healthcare``). NULL for verticals with no section
    and for the legacy application-domains.
  * ``tenants.primary_domain`` (String) -> ``tenants.primary_domain_id`` (UUID
    FK -> domains.id). The chosen vertical's ``branch_compliance_key`` decides
    which single compliance section a tenant's branches seed.

Seeds ``branch_compliance_key`` for the 6 verticals that have a table, matched
by the stable UPPER_SNAKE ``domains.code``.

Defensive: the live master DB drifts from the alembic chain (tables rebuilt via
create_all), so every step is guarded by an existence check.

Revision ID: 040
Revises: 039
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# domains.code (stable UPPER_SNAKE) -> branch_compliance_key
_SEED = {
    "HEALTHCARE_LIFE_SCIENCES":   "entities_healthcare",
    "MANUFACTURING_INDUSTRIAL":   "entities_manufacturing_industrial",
    "RETAIL_ECOMMERCE":           "entities_retail_ecommerce",
    "BANKING_FINANCIAL_SERVICES": "entities_banking_financial",
    "LOGISTICS_SUPPLY_CHAIN":     "logistics_supply_chain",
    "EDUCATION":                  "entities_education",
}


def _cols(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)} if table in inspector.get_table_names() else set()


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    domains_cols = _cols(insp, "domains")
    tenants_cols = _cols(insp, "tenants")

    # 1. domains.branch_compliance_key
    if "domains" in insp.get_table_names() and "branch_compliance_key" not in domains_cols:
        op.add_column("domains", sa.Column("branch_compliance_key", sa.String(64), nullable=True))
        op.create_index("ix_domains_branch_compliance_key", "domains", ["branch_compliance_key"])

    # 2. seed the 6 verticals (only fill NULLs, matched by code)
    if "domains" in insp.get_table_names():
        for code, key in _SEED.items():
            bind.execute(
                sa.text(
                    "UPDATE domains SET branch_compliance_key = :key "
                    "WHERE code = :code AND branch_compliance_key IS NULL"
                ),
                {"key": key, "code": code},
            )

    # 3. tenants.primary_domain_id
    if "tenants" in insp.get_table_names() and "primary_domain_id" not in tenants_cols:
        op.add_column("tenants", sa.Column("primary_domain_id", UUID(as_uuid=True), nullable=True))
        op.create_index("ix_tenants_primary_domain_id", "tenants", ["primary_domain_id"])
        op.create_foreign_key(
            "fk_tenants_primary_domain_id_domains",
            "tenants", "domains", ["primary_domain_id"], ["id"],
        )

    # 4. best-effort backfill from the legacy primary_domain string
    if "tenants" in insp.get_table_names() and "primary_domain" in tenants_cols:
        bind.execute(sa.text(
            "UPDATE tenants t SET primary_domain_id = d.id "
            "FROM domains d "
            "WHERE t.primary_domain_id IS NULL AND t.primary_domain IS NOT NULL "
            "AND lower(regexp_replace(t.primary_domain, '[^a-z0-9]', '', 'gi')) IN ("
            "    lower(regexp_replace(d.code, '[^a-z0-9]', '', 'gi')), "
            "    lower(regexp_replace(d.name, '[^a-z0-9]', '', 'gi')))"
        ))

    # 5. drop the legacy column
    if "tenants" in insp.get_table_names() and "primary_domain" in tenants_cols:
        op.drop_column("tenants", "primary_domain")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tenants_cols = _cols(insp, "tenants")
    domains_cols = _cols(insp, "domains")

    if "tenants" in insp.get_table_names() and "primary_domain" not in tenants_cols:
        op.add_column("tenants", sa.Column("primary_domain", sa.String(100), nullable=True))
        if "primary_domain_id" in tenants_cols:
            bind.execute(sa.text(
                "UPDATE tenants t SET primary_domain = d.name "
                "FROM domains d WHERE t.primary_domain_id = d.id AND t.primary_domain IS NULL"
            ))

    if "tenants" in insp.get_table_names() and "primary_domain_id" in tenants_cols:
        try:
            op.drop_constraint("fk_tenants_primary_domain_id_domains", "tenants", type_="foreignkey")
        except Exception:
            pass
        try:
            op.drop_index("ix_tenants_primary_domain_id", table_name="tenants")
        except Exception:
            pass
        op.drop_column("tenants", "primary_domain_id")

    if "domains" in insp.get_table_names() and "branch_compliance_key" in domains_cols:
        try:
            op.drop_index("ix_domains_branch_compliance_key", table_name="domains")
        except Exception:
            pass
        op.drop_column("domains", "branch_compliance_key")
