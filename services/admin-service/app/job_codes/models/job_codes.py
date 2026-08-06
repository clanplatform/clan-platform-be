"""
JobCode SQLAlchemy Models for PostgreSQL

This module contains the SQLAlchemy models for the JobCode system:
- JobCode: Main job codes table
- JobCodeBasicInfo: Basic information (one-to-one with JobCode)
- JobCodeSkills: Skills and requirements (one-to-one with JobCode)

All models are optimized for PostgreSQL with proper relationships,
foreign keys, indexes, and cascade delete functionality.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from app.infrastructure.database.base import Base
import uuid


class JobCode(Base):
    """
    Main JobCode table containing core job code information.
    
    This is the parent table with one-to-one relationships to:
    - JobCodeBasicInfo (detailed job information)
    - JobCodeSkills (skills and requirements)
    """
    __tablename__ = "job_codes"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Core fields
    job_code = Column(String(50), unique=True, nullable=False, index=True,
                     comment="Unique job code identifier")
    job_title = Column(String(150), nullable=False,
                      comment="Job title/position name")
    active_status = Column(Boolean, default=True, nullable=False,
                          comment="Whether the job code is currently active")

    # Derived from the JWT (never accepted/returned in the CRUD schema):
    # NULL -> master-DB user, a tenant -> tenant-DB user. Nullable so master-DB
    # users can create rows in the master DB.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
                      nullable=True, index=True, comment="Foreign key to tenants table")

    # Soft delete: set on DELETE (with active_status=False); rows are
    # permanently purged after the retention period (30 days).
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True,
                       comment="Soft-delete timestamp; permanently purged after retention")

    # Audit fields with PostgreSQL timezone support
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
                       comment="Record creation timestamp")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), 
                       onupdate=func.now(), nullable=False,
                       comment="Record last update timestamp")
    
    # One-to-one relationships with cascade delete
    basic_info = relationship("JobCodeBasicInfo", back_populates="job_code", 
                             uselist=False, cascade="all, delete-orphan",
                             lazy="select")
    skills = relationship("JobCodeSkills", back_populates="job_code", 
                         uselist=False, cascade="all, delete-orphan",
                         lazy="select")
    # Relationship to owning tenant
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    # Table indexes for performance
    __table_args__ = (
        Index('ix_job_codes_active_status', 'active_status'),
        Index('ix_job_codes_job_title', 'job_title'),
        Index('ix_job_codes_created_at', 'created_at'),
        Index('ix_job_codes_composite_search', 'job_code', 'job_title', 'active_status'),
        {'comment': 'Main job codes table with core job information'}
    )
    
    def __repr__(self):
        return f"<JobCode(id={self.id}, job_code='{self.job_code}', title='{self.job_title}')>"


class JobCodeBasicInfo(Base):
    """
    Basic information table for job codes (one-to-one with JobCode).

    Contains detailed job information such as department, division,
    employment type, work mode, experience, and reporting manager.
    """
    __tablename__ = "jobcode_basicinfo"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Foreign key to JobCode (one-to-one relationship)
    job_code_id = Column(UUID(as_uuid=True), ForeignKey("job_codes.id", ondelete="CASCADE"),
                        unique=True, nullable=False, index=True,
                        comment="Foreign key to job_codes table")

    # tenant_id is derived from the JWT (NULL = master-DB user) and never
    # returned in the CRUD schema; entity/department/division stay client-supplied.
    # Nullable so master-DB users can create rows in the master DB.
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
                      nullable=True, index=True, comment="Foreign key to tenants table")
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.entity_id", ondelete="CASCADE"),
                      nullable=False, index=True, comment="Foreign key to entities table")
    department_id = Column(UUID(as_uuid=True), ForeignKey("departments.department_id", ondelete="CASCADE"), 
                          nullable=False, index=True, comment="Foreign key to departments table")
    division_id = Column(UUID(as_uuid=True), ForeignKey("divisions.id", ondelete="CASCADE"), 
                        nullable=False, index=True, comment="Foreign key to divisions table")
    
    # Employment details
    employment_type = Column(String(50),
                           comment="Employment type (Full-time, Contract, Part-time)")
    work_mode = Column(String(50),
                      comment="Work mode (Onsite, Remote, Hybrid)")
    grade_band = Column(String(50), comment="Grade / band (e.g. L4 / Band 3)")

    # Salary information (matching schema)
    minimum_salary = Column(Integer, comment="Minimum salary")
    maximum_salary = Column(Integer, comment="Maximum salary")
    salary_currency = Column(String(10), comment="Salary currency (e.g. USD)")
    
    # Experience and reporting (matching schema)
    experience_years = Column(Integer, comment="Required experience in years")
    reports_to = Column(String(50), comment="Reporting manager or position")
    
    # Audit fields with PostgreSQL timezone support
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
                       comment="Record creation timestamp")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), 
                       onupdate=func.now(), nullable=False,
                       comment="Record last update timestamp")
    
    # Relationship back to JobCode
    job_code = relationship("JobCode", back_populates="basic_info")
    
    # Relationships to organizational entities
    tenant = relationship("Tenant", foreign_keys=[tenant_id])
    entity = relationship("Entity", foreign_keys=[entity_id])
    department = relationship("Department", foreign_keys=[department_id])
    division = relationship("Division", foreign_keys=[division_id])
    
    # Table indexes for performance
    __table_args__ = (
        Index('ix_jobcode_basicinfo_department_division', 'department_id', 'division_id'),
        Index('ix_jobcode_basicinfo_employment_work', 'employment_type', 'work_mode'),
        {'comment': 'Basic information for job codes with organizational details'}
    )

    def __repr__(self):
        return f"<JobCodeBasicInfo(id={self.id}, job_code_id={self.job_code_id})>"


class JobCodeSkills(Base):
    """
    Skills and requirements table for job codes (one-to-one with JobCode).

    Contains information about key responsibilities and required skills.
    """
    __tablename__ = "jobcode_skills"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)

    # Foreign key to JobCode (one-to-one relationship)
    job_code_id = Column(UUID(as_uuid=True), ForeignKey("job_codes.id", ondelete="CASCADE"),
                        unique=True, nullable=False, index=True,
                        comment="Foreign key to job_codes table")

    # Responsibilities and skills
    key_responsibilities = Column(Text, comment="Key job responsibilities and duties")
    required_skills = Column(Text, comment="Required technical and soft skills")

    # Audit fields with PostgreSQL timezone support
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False,
                       comment="Record creation timestamp")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(),
                       onupdate=func.now(), nullable=False,
                       comment="Record last update timestamp")

    # Relationship back to JobCode
    job_code = relationship("JobCode", back_populates="skills")

    # Table indexes for performance
    __table_args__ = (
        {'comment': 'Skills and requirements for job codes'}
    )

    def __repr__(self):
        return f"<JobCodeSkills(id={self.id}, job_code_id={self.job_code_id})>"