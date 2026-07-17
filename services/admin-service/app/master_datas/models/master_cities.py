from sqlalchemy import Column, String, DateTime, Boolean, Integer, Numeric, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class MasterCity(Base):
    __tablename__ = "master_cities"
    __table_args__ = (
        # City names repeat across states (Springfield), so the name is unique per state.
        # postal_code is deliberately not constrained: it is a representative code here,
        # and real postal codes are neither one-per-city nor unique across a state.
        UniqueConstraint("state_id", "city_name", name="uq_master_cities_state_name"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_id = Column(
        UUID(as_uuid=True),
        ForeignKey("master_states.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    city_name = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=True, index=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)

    display_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    state = relationship("MasterState", back_populates="cities")

    def __repr__(self):
        return f"<MasterCity(id={self.id}, name={self.city_name}, state_id={self.state_id})>"
