from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func
from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime
import logging

from app.entities.models.entity import Entity
from app.entities.schemas.entity import EntityCreate, EntityUpdate
from app.entities.exceptions import (
    EntityNotFoundError,
    DuplicateEntityCodeError,
)
from app.core.hybrid_encryption import hybrid_encryption

logger = logging.getLogger(__name__)


def _utc_offset_for_zone(tz_name: str) -> Optional[str]:
    """Current UTC offset for an IANA zone as '+05:30' / '-04:00' (DST-aware)."""
    try:
        from zoneinfo import ZoneInfo
        offset = datetime.now(ZoneInfo(tz_name)).utcoffset()
        if offset is None:
            return None
        total_minutes = int(offset.total_seconds() // 60)
        sign = "+" if total_minutes >= 0 else "-"
        hours, minutes = divmod(abs(total_minutes), 60)
        return f"{sign}{hours:02d}:{minutes:02d}"
    except Exception:
        return None


def _derive_locale_fields(country_code: Optional[str]) -> Dict[str, Optional[str]]:
    """
    Autogenerate the entity locale fields from the given country. These are
    never taken from the request or the server's local system.

    - time_zone               <- master_countries.timezone (IANA, e.g. Asia/Kolkata)
    - time_zone_offset        <- computed from that IANA zone (DST-aware)
    - date_format/time_format <- the country's master_locales row (default preferred)
    - date_time_format        <- "<date_format> <time_format>"

    Master data lives in the MASTER database; entities may be written to a
    tenant DB, so this opens its own master session. Best-effort: anything that
    cannot be resolved (unknown country, empty master data) stays None and the
    entity write proceeds.
    """
    derived: Dict[str, Optional[str]] = {
        "time_zone": None,
        "time_zone_offset": None,
        "date_format": None,
        "time_format": None,
        "date_time_format": None,
    }
    if not country_code or not country_code.strip():
        return derived

    from app.infrastructure.database.session import SessionLocal
    from app.master_datas.models.master_countries import MasterCountry
    from app.master_datas.models.master_locales import MasterLocale

    master_db = SessionLocal()
    try:
        code = country_code.strip().upper()
        country = master_db.query(MasterCountry).filter(
            sa_func.upper(MasterCountry.iso2_code) == code
        ).first() or master_db.query(MasterCountry).filter(
            sa_func.upper(MasterCountry.iso3_code) == code
        ).first()
        if not country:
            logger.info("[ENTITY_LOCALE] No master country for code=%s; locale fields left empty", code)
            return derived

        if country.timezone:
            derived["time_zone"] = country.timezone
            derived["time_zone_offset"] = _utc_offset_for_zone(country.timezone)

        locale = master_db.query(MasterLocale).filter(
            MasterLocale.country_id == country.id,
            MasterLocale.is_active == True,
        ).order_by(MasterLocale.is_default.desc()).first()
        if locale:
            derived["date_format"] = locale.date_format
            derived["time_format"] = locale.time_format
            if locale.date_format and locale.time_format:
                derived["date_time_format"] = f"{locale.date_format} {locale.time_format}"

        # Clamp to the entities column widths (master data columns are wider)
        _limits = {"time_zone": 50, "time_zone_offset": 10, "date_format": 20,
                   "time_format": 20, "date_time_format": 40}
        return {k: (v[:_limits[k]] if isinstance(v, str) else v) for k, v in derived.items()}
    except Exception as exc:
        logger.warning("[ENTITY_LOCALE] Derivation failed for country=%s: %s", country_code, exc)
        return derived
    finally:
        master_db.close()

def get_entity(db: Session, entity_id: int) -> Optional[Entity]:
    """Get an entity by ID"""
    entity = db.query(Entity).filter(Entity.entity_id == entity_id, Entity.deleted == False).first()
    if entity:
        _decrypt_entity_fields(entity)
    return entity

def _decrypt_entity_fields(entity: Entity) -> None:
    """Decrypt sensitive fields in entity object"""
    # Add decryption for sensitive fields if needed
    pass

def get_entity_by_code(db: Session, entity_code: str) -> Optional[Entity]:
    """Get an entity by code"""
    entity = db.query(Entity).filter(Entity.entity_code == entity_code, Entity.deleted == False).first()
    if entity:
        _decrypt_entity_fields(entity)
    return entity

def get_entities(db: Session, skip: int = 0, limit: int = 100) -> List[Entity]:
    """Get all entities with pagination"""
    entities = db.query(Entity).filter(Entity.deleted == False).offset(skip).limit(limit).all()
    for entity in entities:
        _decrypt_entity_fields(entity)
    return entities

def create_entity(
    db: Session,
    entity: EntityCreate,
    tenant_id: Optional[UUID],
    user_id: Optional[UUID] = None,
    entity_id: Optional[UUID] = None,
) -> Entity:
    """Create a new entity.

    tenant_id is not part of the request body — it is derived from the caller's
    JWT and passed in here so the column stays populated while remaining absent
    from the CRUD schema. It is None for master-DB users (token without a
    tenant_id) and a tenant UUID for tenant-DB users.

    entity_id lets a caller supply the primary key instead of letting the DB
    generate one (used by onboarding, where the client generates branch UUIDs so
    departments/divisions/etc can reference them in the same request). When None,
    the model's uuid4 default applies.
    """
    # Check if entity code already exists
    db_entity = get_entity_by_code(db, entity_code=entity.entity_code)
    if db_entity:
        raise DuplicateEntityCodeError(entity.entity_code)

    # Create new entity
    entity_data = entity.model_dump()

    # Locale fields are autogenerated from the country's master data. A
    # caller-supplied timezone (branch "Timezone") overrides the derived one and
    # its UTC offset is recomputed from the chosen zone.
    locale_fields = _derive_locale_fields(entity_data.get('country'))
    if entity_data.get('time_zone'):
        locale_fields['time_zone'] = entity_data['time_zone']
        locale_fields['time_zone_offset'] = (
            _utc_offset_for_zone(entity_data['time_zone']) or locale_fields['time_zone_offset']
        )

    # Create entity without updated_at to avoid constraint issues
    db_entity = Entity(
        entity_name=entity_data['entity_name'],
        entity_code=entity_data['entity_code'],
        company_size=entity_data.get('company_size'),
        contact=entity_data.get('contact'),
        email=entity_data.get('email'),
        tenant_id=tenant_id,
        address_1=entity_data.get('address_1'),
        address_2=entity_data.get('address_2'),
        city=entity_data.get('city'),
        state=entity_data.get('state'),
        country=entity_data.get('country'),
        location_type=entity_data.get('location_type'),
        is_headquarters=entity_data.get('is_headquarters', False),
        phone=entity_data.get('phone'),
        tax_registration=entity_data.get('tax_registration'),
        postal_code=entity_data.get('postal_code'),
        working_days=entity_data.get('working_days'),
        business_hours_start=entity_data.get('business_hours_start'),
        business_hours_end=entity_data.get('business_hours_end'),
        observes_dst=entity_data.get('observes_dst', False),
        business_registration_doc=entity_data.get('business_registration_doc'),
        tax_certificate_doc=entity_data.get('tax_certificate_doc'),
        incorporation_certificate_doc=entity_data.get('incorporation_certificate_doc'),
        data_processing_agreement_doc=entity_data.get('data_processing_agreement_doc'),
        insurance_certificate_doc=entity_data.get('insurance_certificate_doc'),
        other_documents_doc=entity_data.get('other_documents_doc'),
        time_zone=locale_fields['time_zone'],
        time_zone_offset=locale_fields['time_zone_offset'],
        date_format=locale_fields['date_format'],
        time_format=locale_fields['time_format'],
        date_time_format=locale_fields['date_time_format']
    )
    # Honor a caller-supplied primary key (onboarding); otherwise the model's
    # uuid4 default generates one.
    if entity_id is not None:
        db_entity.entity_id = entity_id
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    # Audit logging happens in the route layer (richer request context).
    return db_entity

def update_entity(db: Session, entity_id: int, entity: EntityUpdate, user_id: Optional[UUID] = None) -> Optional[Entity]:
    """Update an entity"""
    db_entity = get_entity(db, entity_id=entity_id)
    if not db_entity:
        raise EntityNotFoundError()

    update_data = entity.model_dump(exclude_unset=True)

    # Check code uniqueness if being updated
    if "entity_code" in update_data and update_data["entity_code"] != db_entity.entity_code:
        if get_entity_by_code(db, entity_code=update_data["entity_code"]):
            raise DuplicateEntityCodeError(update_data["entity_code"])

    for key, value in update_data.items():
        setattr(db_entity, key, value)

    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    # Audit logging happens in the route layer (richer request context).
    return db_entity

def delete_entity(db: Session, entity_id: int, user_id: Optional[UUID] = None) -> bool:
    """Soft delete an entity"""
    db_entity = get_entity(db, entity_id=entity_id)
    if not db_entity:
        return False

    db_entity.deleted = True
    db_entity.active = False
    db.add(db_entity)
    db.commit()
    # Audit logging happens in the route layer (richer request context).
    return True

def get_entities_count(db: Session) -> int:
    """Get total count of all entities"""
    return db.query(Entity).filter(Entity.deleted == False).count()

def get_entities_by_location(db: Session, country: str = None, state: str = None, city: str = None, skip: int = 0, limit: int = 100) -> List[Entity]:
    """Get entities by location filters"""
    query = db.query(Entity).filter(Entity.deleted == False)

    if country:
        query = query.filter(Entity.country == country)
    if state:
        query = query.filter(Entity.state == state)
    if city:
        query = query.filter(Entity.city == city)
    
    entities = query.offset(skip).limit(limit).all()
    for entity in entities:
        _decrypt_entity_fields(entity)
    return entities