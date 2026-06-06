from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class FormLanguageBase(BaseModel):
    """Base schema for FormLanguage"""
    lang_code: str = Field(..., min_length=1, max_length=10, description="Language code (e.g., 'en', 'es', 'fr')")
    language: str = Field(..., min_length=1, max_length=100, description="Language name (e.g., 'English', 'Spanish', 'French')")
    app_form_entity_type: str = Field(..., min_length=1, max_length=100, description="Entity type (e.g., 'form', 'field', 'section')")
    app_form_entity_id: UUID = Field(..., description="Form entity ID (foreign key to forms table)")
    translated_name: Optional[str] = Field(None, max_length=255, description="Translated name")
    type: Optional[str] = Field(None, max_length=100, description="Translation type (e.g., 'label', 'placeholder', 'help_text', 'error_message')")
    value: Optional[str] = Field(None, description="Translation value")
    key: Optional[str] = Field(None, max_length=255, description="Translation key")
    error_message: Optional[str] = Field(None, description="Error message translation")


class FormLanguageCreate(FormLanguageBase):
    """Schema for creating a new form language entry"""
    pass


class FormLanguageUpdate(BaseModel):
    """Schema for updating an existing form language entry"""
    lang_code: Optional[str] = Field(None, min_length=1, max_length=10, description="Language code")
    language: Optional[str] = Field(None, min_length=1, max_length=100, description="Language name")
    app_form_entity_type: Optional[str] = Field(None, min_length=1, max_length=100, description="Entity type")
    app_form_entity_id: Optional[UUID] = Field(None, description="Form entity ID")
    translated_name: Optional[str] = Field(None, max_length=255, description="Translated name")
    type: Optional[str] = Field(None, max_length=100, description="Translation type")
    value: Optional[str] = Field(None, description="Translation value")
    key: Optional[str] = Field(None, max_length=255, description="Translation key")
    error_message: Optional[str] = Field(None, description="Error message translation")


class FormLanguageResponse(FormLanguageBase):
    """Schema for form language response"""
    id: UUID
    sino: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FormLanguageBulkCreate(BaseModel):
    """Schema for bulk creating form language entries"""
    translations: list[FormLanguageCreate] = Field(..., description="List of form language translations to create")


class FormLanguageBulkResponse(BaseModel):
    """Schema for bulk create response"""
    created_count: int = Field(..., description="Number of translations created")
    translations: list[FormLanguageResponse] = Field(..., description="Created translations")
