from sqlalchemy import Column, String, DateTime, Boolean, Integer, SmallInteger, CHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class MasterCountry(Base):
    __tablename__ = "master_countries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    country_name = Column(String(100), nullable=False, unique=True, index=True)
    iso2_code = Column(CHAR(2), nullable=False, unique=True, index=True)
    iso3_code = Column(CHAR(3), nullable=False, unique=True, index=True)
    numeric_code = Column(SmallInteger, nullable=True, unique=True)
    phone_code = Column(String(10), nullable=True)
    currency_code = Column(CHAR(3), nullable=True, index=True)
    timezone = Column(String(100), nullable=True)
    nationality = Column(String(100), nullable=True)
    flag_emoji = Column(String(10), nullable=True)

    display_order = Column(Integer, nullable=False, default=0)
    # Only one row may carry is_default=True; the service enforces this.
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    states = relationship("MasterState", back_populates="country")
    locales = relationship("MasterLocale", back_populates="country")

    def __repr__(self):
        return f"<MasterCountry(id={self.id}, iso2={self.iso2_code}, name={self.country_name})>"
