"""
Branch compliance-section registry + vertical resolution.

A tenant has one industry vertical (``tenants.primary_domain_id`` -> ``domains``).
Each vertical that has a branch-form compliance section carries a
``domains.branch_compliance_key`` — a literal string that is, by contract,
simultaneously:

  * a nested field name on ``OnboardingBranch`` / ``EntityBase`` / ``EntityResponse``
  * the ``__tablename__`` of that section's SQLAlchemy model
  * a key in ``SECTION_REGISTRY`` below

So resolving "which nested object in branches do we seed" is just:

    key = resolve_branch_compliance_key(tenant_id)      # -> "entities_healthcare" | None
    schema_cls, sync_fn = SECTION_REGISTRY[key]
    sync_fn(db, entity_id, tenant_id, getattr(branch_payload, key, None))

Verticals with no compliance section (Technology, Non-profit, …) and tenants
with no vertical resolve to ``None`` -> nothing is seeded.
"""
import logging
from typing import Callable, Dict, Optional, Tuple, Type
from uuid import UUID

from pydantic import BaseModel

from app.infrastructure.database.base import Base

from app.entities.schemas.entities_healthcare import EntitiesHealthcareCreate
from app.entities.schemas.entities_manufacturing_industrial import EntitiesManufacturingIndustrialCreate
from app.entities.schemas.entities_retail_ecommerce import EntitiesRetailEcommerceCreate
from app.entities.schemas.entities_banking_financial import EntitiesBankingFinancialCreate
from app.entities.schemas.logistics_supply_chain import LogisticsSupplyChainCreate
from app.entities.schemas.entities_education import EntitiesEducationCreate

from app.entities.services.entities_healthcare import (
    sync_entities_healthcare_rows, soft_delete_entities_healthcare_rows,
)
from app.entities.services.entities_manufacturing_industrial import (
    sync_entities_manufacturing_industrial_rows, soft_delete_entities_manufacturing_industrial_rows,
)
from app.entities.services.entities_retail_ecommerce import (
    sync_entities_retail_ecommerce_rows, soft_delete_entities_retail_ecommerce_rows,
)
from app.entities.services.entities_banking_financial import (
    sync_entities_banking_financial_rows, soft_delete_entities_banking_financial_rows,
)
from app.entities.services.logistics_supply_chain import (
    sync_logistics_supply_chain_rows, soft_delete_logistics_supply_chain_rows,
)
from app.entities.services.entities_education import (
    sync_entities_education_rows, soft_delete_entities_education_rows,
)

logger = logging.getLogger(__name__)

# branch_compliance_key  ->  (nested-item Create schema, sync fn, soft-delete fn)
SECTION_REGISTRY: Dict[str, Tuple[Type[BaseModel], Callable, Callable]] = {
    "entities_healthcare":               (EntitiesHealthcareCreate,             sync_entities_healthcare_rows,             soft_delete_entities_healthcare_rows),
    "entities_manufacturing_industrial": (EntitiesManufacturingIndustrialCreate, sync_entities_manufacturing_industrial_rows, soft_delete_entities_manufacturing_industrial_rows),
    "entities_retail_ecommerce":         (EntitiesRetailEcommerceCreate,        sync_entities_retail_ecommerce_rows,       soft_delete_entities_retail_ecommerce_rows),
    "entities_banking_financial":        (EntitiesBankingFinancialCreate,       sync_entities_banking_financial_rows,      soft_delete_entities_banking_financial_rows),
    "logistics_supply_chain":            (LogisticsSupplyChainCreate,           sync_logistics_supply_chain_rows,          soft_delete_logistics_supply_chain_rows),
    "entities_education":                (EntitiesEducationCreate,              sync_entities_education_rows,              soft_delete_entities_education_rows),
}

# The set of branch-form nested keys that map to a compliance table.
SECTION_KEYS = frozenset(SECTION_REGISTRY)


def resolve_branch_compliance_key(tenant_id: Optional[UUID]) -> Optional[str]:
    """The compliance section key for a tenant's industry vertical, or None.

    None when: tenant_id is None (master-DB / platform branch), the tenant has
    no primary_domain_id, the vertical has no branch_compliance_key, or anything
    fails. Opens its own MASTER session (like _derive_locale_fields) — the
    caller may be operating on a tenant DB.
    """
    if not tenant_id:
        return None
    try:
        from app.infrastructure.database.session import SessionLocal
        from app.tenants.models.tenants import Tenant
        from app.domains.models.domain import Domain

        master_db = SessionLocal()
        try:
            key = (
                master_db.query(Domain.branch_compliance_key)
                .join(Tenant, Tenant.primary_domain_id == Domain.id)
                .filter(Tenant.tenant_id == tenant_id)
                .scalar()
            )
            return key or None
        finally:
            master_db.close()
    except Exception as exc:  # never break an entity write over this
        logger.warning("[COMPLIANCE] vertical resolution failed for tenant=%s: %s", tenant_id, exc)
        return None


# --- Contract checks — fail fast at import time on a typo ---------------------
_missing_tables = sorted(k for k in SECTION_REGISTRY if k not in Base.metadata.tables)
assert not _missing_tables, f"SECTION_REGISTRY keys with no matching table: {_missing_tables}"

try:
    from app.entities.schemas.entity import EntityBase

    _missing_fields = sorted(k for k in SECTION_REGISTRY if k not in EntityBase.model_fields)
    assert not _missing_fields, f"SECTION_REGISTRY keys not declared on EntityBase: {_missing_fields}"
except ImportError:  # pragma: no cover - EntityBase pulls in entity.py; tolerate partial import graphs
    pass
