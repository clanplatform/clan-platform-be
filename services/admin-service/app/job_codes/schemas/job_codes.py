"""
JobCode Pydantic Schemas for API Validation and Serialization

This module defines Pydantic schemas for:
- JobCode
- JobCodeBasicInfo
- JobCodeSkills
- JobCodeBenefits

Includes:
- Base schemas for shared attributes
- Create schemas (POST)
- Update schemas (PUT/PATCH)
- Read schemas (GET)
- Standard response formats
"""

from typing import Optional, List, Union
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Base Schemas
# ============================================================================

class JobCodeBase(BaseModel):
    """Core JobCode fields"""
    job_code: str = Field(..., max_length=50, description="Unique job code identifier")
    job_title: str = Field(..., max_length=150, description="Job title/position name")
    active_status: bool = Field(default=True, description="Whether the job code is currently active")


class JobCodeBasicInfoBase(BaseModel):
    """Base for job basic information"""
    category: Optional[str] = Field(None, max_length=100)
    level: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    # Required organizational hierarchy fields with proper UUID types
    tenant_id: UUID = Field(..., description="Tenant UUID - required for organizational hierarchy")
    entity_id: UUID = Field(..., description="Entity UUID - required for organizational hierarchy")
    department_id: UUID = Field(..., description="Department UUID - required for organizational hierarchy")
    division_id: UUID = Field(..., description="Division UUID - required for organizational hierarchy")
    employment_type: Optional[str] = Field(None, max_length=50)
    work_mode: Optional[str] = Field(None, max_length=50)
    minimum_salary: Optional[int] = Field(None)
    maximum_salary: Optional[int] = Field(None)
    experience_years: Optional[int] = Field(None)
    reports_to: Optional[str] = Field(None, max_length=100)


class JobCodeSkillsBase(BaseModel):
    """Base for job skills and qualifications"""
    key_responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    required_skills: Optional[str] = None
    education_level: Optional[str] = Field(None, max_length=100)
    certifications: Optional[str] = None
    performance_metrics: Optional[str] = None


class JobCodeBenefitsBase(BaseModel):
    """Base for job benefits"""
    benefits_package: Optional[str] = None


# ============================================================================
# Create Schemas
# ============================================================================

class JobCodeBasicInfoCreate(JobCodeBasicInfoBase):
    pass


class JobCodeSkillsCreate(JobCodeSkillsBase):
    pass


class JobCodeBenefitsCreate(JobCodeBenefitsBase):
    pass


class JobCodeCreate(JobCodeBase):
    """Main create schema with nested relationships"""
    basic_info: Optional[JobCodeBasicInfoCreate] = None
    skills: Optional[JobCodeSkillsCreate] = None
    benefits: Optional[JobCodeBenefitsCreate] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "job_code": "ENG-SSE-001",
                "job_title": "Senior Software Engineer",
                "active_status": True,
                "basic_info": {
                    "category": "Engineering",
                    "level": "Senior",
                    "description": "Responsible for backend architecture and APIs.",
                    "tenant_id": "d697b099-e6d0-4bdb-9cbe-c3495474e0a7",
                    "entity_id": "bf5b788b-2e9e-407b-9c68-7c8dded6b2d9",
                    "department_id": "7ca82431-ca5f-4234-9cb3-e5564c08b00e",
                    "division_id": "b4bbb063-6158-4e29-aed9-e678581bf1f1",
                    "employment_type": "Full-time",
                    "work_mode": "Hybrid",
                    "minimum_salary": 85000,
                    "maximum_salary": 120000,
                    "experience_years": 5,
                    "reports_to": "Engineering Director"
                },
                "skills": {
                    "key_responsibilities": "Design and implement scalable APIs",
                    "requirements": "Strong Python and FastAPI experience",
                    "required_skills": "Python, FastAPI, SQLAlchemy, Docker",
                    "education_level": "Bachelor’s Degree",
                    "certifications": "AWS Developer Certification",
                    "performance_metrics": "Code quality, delivery speed"
                },
                "benefits": {
                    "benefits_package": "Health, Dental, 401k, Remote flexibility"
                }
            }
        }
    )


# ============================================================================
# Update Schemas
# ============================================================================

class JobCodeBasicInfoUpdate(JobCodeBasicInfoBase):
    pass


class JobCodeSkillsUpdate(JobCodeSkillsBase):
    pass


class JobCodeBenefitsUpdate(JobCodeBenefitsBase):
    pass


class JobCodeUpdate(BaseModel):
    job_code: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=150)
    active_status: Optional[bool] = None
    basic_info: Optional[JobCodeBasicInfoUpdate] = None
    skills: Optional[JobCodeSkillsUpdate] = None
    benefits: Optional[JobCodeBenefitsUpdate] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Read Schemas
# ============================================================================

class JobCodeBasicInfoRead(JobCodeBasicInfoBase):
    id: UUID
    job_code_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobCodeSkillsRead(JobCodeSkillsBase):
    id: UUID
    job_code_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobCodeBenefitsRead(JobCodeBenefitsBase):
    id: UUID
    job_code_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobCodeRead(JobCodeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    basic_info: Optional[JobCodeBasicInfoRead] = None
    skills: Optional[JobCodeSkillsRead] = None
    benefits: Optional[JobCodeBenefitsRead] = None

    model_config = ConfigDict(from_attributes=True)


class JobCodeReadSimple(JobCodeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Standard Response Schemas
# ============================================================================

class JobCodeResponse(BaseModel):
    success: bool = True
    message: str = "Operation successful"
    data: JobCodeRead

    model_config = ConfigDict(from_attributes=True)


class JobCodeCreateResponse(BaseModel):
    success: bool = True
    message: str = "Job code created successfully"
    data: JobCodeRead

    model_config = ConfigDict(from_attributes=True)


class JobCodeUpdateResponse(BaseModel):
    success: bool = True
    message: str = "Job code updated successfully"
    data: JobCodeRead

    model_config = ConfigDict(from_attributes=True)


class JobCodeListResponse(BaseModel):
    success: bool = True
    message: str = "Job codes retrieved successfully"
    data: List[JobCodeRead]
    total: int
    page: int = 1
    per_page: int = 10

    model_config = ConfigDict(from_attributes=True)


class JobCodeDeleteResponse(BaseModel):
    success: bool = True
    message: str = "Job code deleted successfully"
    deleted_id: UUID

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Error Handling Schemas
# ============================================================================

class JobCodeValidationError(BaseModel):
    field: str
    message: str
    value: Optional[Union[str, int, float, bool]] = None

    model_config = ConfigDict(from_attributes=True)


class JobCodeErrorResponse(BaseModel):
    success: bool = False
    message: str
    errors: List[JobCodeValidationError] = []
    error_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Search and Bulk Operations Schemas
# ============================================================================

class JobCodeSearchParams(BaseModel):
    job_code: Optional[str] = None
    job_title: Optional[str] = None
    category: Optional[str] = None
    active_status: Optional[bool] = None
    min_salary_range: Optional[int] = None
    max_salary_range: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class JobCodeBulkCreateRequest(BaseModel):
    job_codes: List[JobCodeCreate]

    model_config = ConfigDict(from_attributes=True)


class JobCodeBulkCreateResponse(BaseModel):
    success: bool = True
    message: str = "Bulk job codes created successfully"
    data: List[JobCodeRead]
    created_count: int
    failed_count: int = 0
    errors: List[JobCodeValidationError] = []

    model_config = ConfigDict(from_attributes=True)
