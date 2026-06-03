from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class DomainBase(BaseModel):
    code: str = Field(..., min_length=1, max_length=50, description="Domain code")
    name: str = Field(..., min_length=1, max_length=100, description="Domain name")
    description: Optional[str] = Field(None, description="Domain description")
    domain_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Domain metadata")
    is_active: Optional[bool] = Field(True, description="Whether the domain is active")

class DomainCreate(DomainBase):
    pass

class DomainUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=50, description="Domain code")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Domain name")
    description: Optional[str] = Field(None, description="Domain description")
    domain_metadata: Optional[Dict[str, Any]] = Field(None, description="Domain metadata")
    is_active: Optional[bool] = Field(None, description="Whether the domain is active")

class DomainResponse(DomainBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
