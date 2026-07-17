from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class MasterLocale(Base):
    __tablename__ = "master_locales"
    __table_args__ = (
        # One locale per language/country pairing. country_id is nullable and
        # Postgres treats NULLs as distinct, so language-only locales ("en") are
        # not constrained by this — locale_code stays the real guard for those.
        UniqueConstraint("language_id", "country_id", name="uq_master_locales_language_country"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    locale_code = Column(String(20), nullable=False, unique=True, index=True)
    locale_name = Column(String(100), nullable=False, unique=True, index=True)

    language_id = Column(
        UUID(as_uuid=True),
        ForeignKey("master_languages.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable: a locale may be language-only ("en") with no region component.
    country_id = Column(
        UUID(as_uuid=True),
        ForeignKey("master_countries.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    date_format = Column(String(30), nullable=True)
    time_format = Column(String(20), nullable=True)
    number_format = Column(String(30), nullable=True)

    # Only one row may carry is_default=True; the service enforces this.
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    language = relationship("MasterLanguage", back_populates="locales")
    country = relationship("MasterCountry", back_populates="locales")

    def __repr__(self):
        return f"<MasterLocale(id={self.id}, code={self.locale_code})>"
