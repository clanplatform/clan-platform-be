from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime


class AuditLogCreate(BaseModel):
    user_id: Optional[UUID] = None
    client_id: Optional[UUID] = None
    entity_id: Optional[UUID] = None
    action: str = Field(..., max_length=100)
    object_type: str = Field(..., max_length=100)
    object_id: Optional[str] = Field(None, max_length=255)
    old_values: Optional[Dict[str, Any]] = {}
    new_values: Optional[Dict[str, Any]] = {}
    ip_address: Optional[str] = Field(None, max_length=45)
    user_agent: Optional[str] = None
    session_id: Optional[str] = Field(None, max_length=255)
    risk_score: Optional[str] = Field(None, max_length=20)
    compliance_tags: Optional[List[str]] = []


class AuditLogResponse(BaseModel):
    log_id: UUID
    user_id: Optional[UUID]
    client_id: Optional[UUID]
    entity_id: Optional[UUID]
    action: str
    object_type: str
    object_id: Optional[str]
    old_values: Optional[Dict[str, Any]]
    new_values: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    session_id: Optional[str]
    risk_score: Optional[str]
    compliance_tags: Optional[List[Any]]
    timestamp: datetime

    class Config:
        from_attributes = True
