from sqlalchemy import Column, String, DateTime, Boolean, Integer, CHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class MasterLanguage(Base):
    __tablename__ = "languages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    language_name = Column(String(100), nullable=False, unique=True, index=True)
    native_name = Column(String(100), nullable=True)
    iso639_1 = Column(CHAR(2), nullable=False, unique=True, index=True)
    iso639_2 = Column(CHAR(3), nullable=True, unique=True)
    locale = Column(String(20), nullable=True, unique=True, index=True)
    # "ltr" or "rtl" — enforced by the schema layer.
    text_direction = Column(String(3), nullable=False, default="ltr")

    display_order = Column(Integer, nullable=False, default=0)
    # Only one row may carry is_default=True; the service enforces this.
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    locales = relationship("MasterLocale", back_populates="language")

    def __repr__(self):
        return f"<MasterLanguage(id={self.id}, iso639_1={self.iso639_1}, name={self.language_name})>"
