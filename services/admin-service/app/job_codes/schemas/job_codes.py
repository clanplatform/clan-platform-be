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
    # active_status is intentionally omitted from the schema: it is a backend-
    # operational column (defaulted True on create, toggled by delete/restore),
    # never sent in the request or returned in the response.


class JobCodeBasicInfoBase(BaseModel):
    """Base for job basic information"""
    # category / level / description are backend columns retained on the table but
    # omitted from the schema (not part of the job-code form).
    # Required organizational hierarchy fields with proper UUID types.
    # tenant_id is intentionally omitted: it is derived from the JWT server-side,
    # never sent in the request or returned in the response.
    entity_id: UUID = Field(..., description="Entity UUID - required for organizational hierarchy")
    department_id: UUID = Field(..., description="Department UUID - required for organizational hierarchy")
    division_id: UUID = Field(..., description="Division UUID - required for organizational hierarchy")
    employment_type: Optional[str] = Field(None, max_length=50)
    work_mode: Optional[str] = Field(None, max_length=50)
    grade_band: Optional[str] = Field(None, max_length=50, description="Grade / band (e.g. L4 / Band 3)")
    minimum_salary: Optional[int] = Field(None)
    maximum_salary: Optional[int] = Field(None)
    salary_currency: Optional[str] = Field(None, max_length=10, description="Salary currency (e.g. USD)")
    experience_years: Optional[int] = Field(None)
    reports_to: Optional[str] = Field(None, max_length=100)


class JobCodeSkillsBase(BaseModel):
    """Base for job skills and qualifications.

    requirements / education_level / certifications / performance_metrics are
    backend columns retained on the table but omitted from the schema (not part
    of the job-code form).
    """
    key_responsibilities: Optional[str] = None
    required_skills: Optional[str] = None


# ============================================================================
# Create Schemas
# ============================================================================

class JobCodeBasicInfoCreate(JobCodeBasicInfoBase):
    pass


class JobCodeSkillsCreate(JobCodeSkillsBase):
    pass


class JobCodeCreate(JobCodeBase):
    """Main create schema with nested relationships"""
    # basic_info is required (it carries entity/department/division). tenant_id
    # is NOT part of it — the service fills both job_codes.tenant_id and
    # jobcode_basicinfo.tenant_id from the caller's JWT.
    basic_info: JobCodeBasicInfoCreate
    skills: Optional[JobCodeSkillsCreate] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "job_code": "ENG-SSE-001",
                "job_title": "Senior Software Engineer",
                "basic_info": {
                    "entity_id": "bf5b788b-2e9e-407b-9c68-7c8dded6b2d9",
                    "department_id": "7ca82431-ca5f-4234-9cb3-e5564c08b00e",
                    "division_id": "b4bbb063-6158-4e29-aed9-e678581bf1f1",
                    "employment_type": "Full-time",
                    "work_mode": "Hybrid",
                    "grade_band": "L4 / Band 3",
                    "minimum_salary": 85000,
                    "maximum_salary": 120000,
                    "salary_currency": "USD",
                    "experience_years": 5,
                    "reports_to": "Engineering Director"
                },
                "skills": {
                    "key_responsibilities": "Design and implement scalable APIs",
                    "required_skills": "Python, FastAPI, SQLAlchemy, Docker"
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


class JobCodeUpdate(BaseModel):
    job_code: Optional[str] = Field(None, max_length=50)
    job_title: Optional[str] = Field(None, max_length=150)
    basic_info: Optional[JobCodeBasicInfoUpdate] = None
    skills: Optional[JobCodeSkillsUpdate] = None

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


class JobCodeRead(JobCodeBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    basic_info: Optional[JobCodeBasicInfoRead] = None
    skills: Optional[JobCodeSkillsRead] = None

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
