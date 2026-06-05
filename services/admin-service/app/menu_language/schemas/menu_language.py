from typing import Optional, Literal, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from uuid import UUID


class MenuLanguageBase(BaseModel):
    lang_code: str = Field(..., min_length=1, max_length=10, description="Language code (e.g., 'en', 'es', 'fr')")
    language: str = Field(..., min_length=1, max_length=100, description="Language name (e.g., 'English', 'Spanish', 'Tamil')")
    translated_name: str = Field(..., min_length=1, max_length=255, description="The translated text")
    app_menu_entity_type: Literal["application", "module", "menu"] = Field(..., description="Entity type: 'application', 'module', or 'menu'")
    app_menu_entity_id: UUID = Field(..., description="UUID of the application, module, or menu entity")


class MenuLanguageCreate(MenuLanguageBase):
    """Schema for creating a new menu language entry"""
    pass


class MenuLanguageUpdate(BaseModel):
    """Schema for updating an existing menu language entry"""
    lang_code: Optional[str] = Field(None, min_length=1, max_length=10, description="Language code")
    language: Optional[str] = Field(None, min_length=1, max_length=100, description="Language name")
    translated_name: Optional[str] = Field(None, min_length=1, max_length=255, description="The translated text")
    app_menu_entity_type: Optional[Literal["application", "module", "menu"]] = Field(None, description="Entity type: 'application', 'module', or 'menu'")
    app_menu_entity_id: Optional[UUID] = Field(None, description="UUID of the application, module, or menu entity")


class MenuLanguageResponse(MenuLanguageBase):
    """Schema for menu language response"""
    id: UUID
    sino: int
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# New schemas for translation with entity details
class TranslatedApplication(BaseModel):
    """Application with translation"""
    id: str
    original_name: str
    translated_name: str
    code: Optional[str] = None
    key: Optional[str] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    route: Optional[str] = None
    order_index: Optional[int] = None


class TranslatedModule(BaseModel):
    """Module with translation"""
    id: str
    application_id: str
    original_name: str
    translated_name: str
    code: Optional[str] = None
    key: Optional[str] = None
    label: Optional[str] = None
    icon: Optional[str] = None
    route: Optional[str] = None
    order_index: Optional[int] = None


class TranslatedMenu(BaseModel):
    """Menu with translation"""
    id: str
    application_id: str
    module_id: Optional[str] = None
    original_name: str
    translated_name: str
    label: Optional[str] = None
    icon: Optional[str] = None
    route: Optional[str] = None
    order_index: Optional[int] = None
    parent_menu_id: Optional[str] = None


class TranslationsWithEntitiesResponse(BaseModel):
    """Complete translation response with entity details"""
    applications: List[TranslatedApplication]
    modules: List[TranslatedModule]
    menus: List[TranslatedMenu]


class TranslationMapResponse(BaseModel):
    """Simple translation map response"""
    lang_code: str
    translations: Dict[str, str] = Field(..., description="Map of entity_id to translated_name")
