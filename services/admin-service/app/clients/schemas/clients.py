from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class ClientBase(BaseModel):
    client_name: str
    client_code: Optional[str] = None
    contact_email: str  # Changed from EmailStr to str
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    subscription_plan: Optional[str] = None
    onboarding_status: Optional[str] = None
    employees_count: Optional[int] = None
    location: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = True

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    client_name: Optional[str] = None
    client_code: Optional[str] = None
    contact_email: Optional[str] = None  # Changed from EmailStr to str
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    subscription_plan: Optional[str] = None
    onboarding_status: Optional[str] = None
    employees_count: Optional[int] = None
    location: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ClientResponse(ClientBase):
    client_id: UUID
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_by: Optional[UUID] = None

    class Config:
        from_attributes = True

class ClientListResponse(BaseModel):
    clients: List[ClientResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

class ClientConfigurationStatus(BaseModel):
    client_id: UUID
    has_entities: bool
    entities_count: int
    has_organizational_structure: bool
    departments_count: int
    divisions_count: int
    has_job_codes: bool
    job_codes_count: int
    has_users: bool
    users_count: int
    setup_completion_percentage: int
    recommended_next_steps: List[str]

