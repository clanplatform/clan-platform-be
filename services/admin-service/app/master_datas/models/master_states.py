from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class MasterState(Base):
    __tablename__ = "states"
    __table_args__ = (
        # Names and codes repeat across countries ("CA" is California and Catalonia),
        # so both are unique per country rather than globally.
        UniqueConstraint("country_id", "state_name", name="uq_master_states_country_name"),
        UniqueConstraint("country_id", "state_code", name="uq_master_states_country_code"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    country_id = Column(
        UUID(as_uuid=True),
        ForeignKey("countries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    state_name = Column(String(100), nullable=False)
    state_code = Column(String(20), nullable=True)
    capital = Column(String(100), nullable=True)

    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    country = relationship("MasterCountry", back_populates="states")
    cities = relationship("MasterCity", back_populates="state")

    def __repr__(self):
        return f"<MasterState(id={self.id}, name={self.state_name}, country_id={self.country_id})>"
