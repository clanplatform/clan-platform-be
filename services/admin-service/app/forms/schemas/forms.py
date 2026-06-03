from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
import uuid

# Component access permissions
class ComponentAccess(BaseModel):
    """Access permissions for form components"""
    read: bool = Field(True, description="Can read/view the component")
    write: bool = Field(True, description="Can edit/modify the component")
    disable: bool = Field(False, description="Component is disabled")

# Form component structure
class FormComponent(BaseModel):
    """Base form component structure - simplified"""
    key: str = Field(..., description="Unique component key")
    type: str = Field(..., description="Component type (e.g., AntInput, AntButton)")
    access: Union[str, List[str]] = Field(default_factory=list, description="Access permissions array")
    props: Dict[str, Any] = Field(default_factory=dict, description="Component properties")
    children: List = Field(default_factory=list, description="Child components - empty array")

    @field_validator('access')
    @classmethod
    def validate_access(cls, v):
        """Convert string access to list"""
        if isinstance(v, str):
            return [v] if v else []
        elif isinstance(v, list):
            return v
        else:
            return []

# Language configuration
class Language(BaseModel):
    """Language configuration"""
    code: str = Field(..., description="Language code (e.g., 'en')")
    dialect: str = Field(..., description="Language dialect (e.g., 'US')")
    name: str = Field(..., description="Language name (e.g., 'English')")
    description: str = Field(..., description="Language description")
    bidi: str = Field("ltr", description="Text direction (ltr/rtl)")

# Form structure
class FormStructure(BaseModel):
    """Complete form structure - simplified"""
    key: str = Field(..., description="Form key")
    type: str = Field("Screen", description="Form type")
    props: Dict[str, Any] = Field(default_factory=dict, description="Form properties")
    access: Union[str, List[str]] = Field(default_factory=list, description="Form access permissions")
    children: List = Field(default_factory=list, description="Form components - empty array")

    @field_validator('access')
    @classmethod
    def validate_access(cls, v):
        """Convert string access to list"""
        if isinstance(v, str):
            return [v] if v else []
        elif isinstance(v, list):
            return v
        else:
            return []

# Frontend form item structure (what comes in the forms array)
class FormItem(BaseModel):
    """Individual form item from frontend forms array"""
    form_id: Optional[str] = Field(None, description="Form ID (optional, will be set automatically)")
    name: str = Field(..., description="Form name")
    defaultLanguage: str = Field("en-US", alias="defaultLanguage", description="Default language")
    form: FormStructure = Field(..., description="Complete form structure")
    languages: List[Language] = Field(default_factory=list, description="Supported languages")
    localization: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Localization data")
    modalType: str = Field("AntModal", alias="modalType", description="Modal type")
    tooltipType: str = Field("AntTooltip", alias="tooltipType", description="Tooltip type")
    errorType: str = Field("AntErrorMessage", alias="errorType", description="Error type")
    triggerWhen: Optional[Dict[str, Any]] = Field(None, alias="triggerWhen", description="Trigger condition")
    version: str = Field("1", description="Form version")

    model_config = ConfigDict(populate_by_name=True)

class FormBase(BaseModel):
    """Base form schema"""
    menu_id: uuid.UUID = Field(..., description="Menu ID this form belongs to")
    name: str = Field(..., min_length=1, max_length=100, description="Form name")
    version: str = Field("1.0.0", max_length=20, description="Form version")
    trigger_when: Optional[str] = Field(None, max_length=255, description="Trigger condition")
    
    # Form structure - now stores array of forms
    forms: List[FormItem] = Field(..., description="Array of form items")
    actions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Form actions")
    
    # UI Configuration
    modal_type: str = Field("AntModalAdapter", max_length=50, description="Modal adapter type")
    tooltip_type: str = Field("AntTooltip", max_length=50, description="Tooltip type")
    error_type: str = Field("AntErrorMessage", max_length=50, description="Error message type")
    
    # Localization
    localization: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Localization data")
    languages: List[Language] = Field(default_factory=list, description="Supported languages")
    default_language: str = Field("en-US", max_length=10, description="Default language")

    access: List[str] = Field(
        default=["read"],
        description="Access permissions for this menu (e.g., ['read', 'write', 'disable'])"
    )
    
    # Status
    is_active: bool = Field(True, description="Whether the form is active")
    created_by: Optional[str] = Field(None, max_length=50, description="Created by user")
    updated_by: Optional[str] = Field(None, max_length=50, description="Updated by user")

class FormCreate(FormBase):
    """Schema for creating a form"""
    pass

# Frontend payload structure (with forms array) - now same as FormBase
class FormCreateFromFrontend(BaseModel):
    """Schema for creating a form from frontend payload"""
    menu_id: uuid.UUID = Field(..., description="Menu ID this form belongs to")
    access: Union[str, List[str]] = Field(default_factory=list, description="Access permissions")
    forms: List[FormItem] = Field(..., description="Array of form items (usually contains one item)")

    @field_validator('access')
    @classmethod
    def validate_access(cls, v):
        """Convert string access to list"""
        if isinstance(v, str):
            return [v] if v else []
        elif isinstance(v, list):
            return v
        else:
            return []

    model_config = ConfigDict(populate_by_name=True)

class FormUpdateSimple(BaseModel):
    """Simplified schema for updating forms - matches screenshot structure"""
    menu_id: uuid.UUID = Field(..., description="Menu ID this form belongs to")
    access: Union[str, List[str]] = Field(default_factory=list, description="Access permissions")
    forms: List[FormItem] = Field(..., description="Array of form items")

    @field_validator('access')
    @classmethod
    def validate_access(cls, v):
        """Convert string access to list"""
        if isinstance(v, str):
            return [v] if v else []
        elif isinstance(v, list):
            return v
        else:
            return []

    model_config = ConfigDict(populate_by_name=True)

class FormUpdate(BaseModel):
    """Schema for updating a form"""
    menu_id: Optional[uuid.UUID] = Field(None, description="Menu ID this form belongs to")
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Form name")
    version: Optional[str] = Field(None, max_length=20, description="Form version")
    trigger_when: Optional[str] = Field(None, max_length=255, description="Trigger condition")
    
    # Form structure - now array
    forms: Optional[List[FormItem]] = Field(None, description="Array of form items")
    actions: Optional[Dict[str, Any]] = Field(None, description="Form actions")
    access: List[str] = Field(
        default=["read"],
        description="Access permissions for this menu (e.g., ['read', 'write', 'disable'])"
    )
    
    # UI Configuration
    modal_type: Optional[str] = Field(None, max_length=50, description="Modal adapter type")
    tooltip_type: Optional[str] = Field(None, max_length=50, description="Tooltip type")
    error_type: Optional[str] = Field(None, max_length=50, description="Error message type")
    
    # Localization
    localization: Optional[Dict[str, Any]] = Field(None, description="Localization data")
    languages: Optional[List[Language]] = Field(None, description="Supported languages")
    default_language: Optional[str] = Field(None, max_length=10, description="Default language")
    
    # Status
    is_active: Optional[bool] = Field(None, description="Whether the form is active")
    updated_by: Optional[str] = Field(None, max_length=50, description="Updated by user")

class FormResponse(FormBase):
    """Schema for form response"""
    id: uuid.UUID
    mongo_id: Optional[str] = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    access: List[str] = Field(
        default=["read"],
        description="Access permissions for this menu (e.g., ['read', 'write', 'disable'])"
    )

class FormListResponse(BaseModel):
    """Schema for paginated form list response"""
    forms: List[FormResponse]
    total: int
    page: int
    size: int
    total_pages: int

    model_config = ConfigDict(from_attributes=True)

# Form import/export schemas
class FormImport(BaseModel):
    """Schema for importing form from JSON"""
    name: str = Field(..., description="Form name")
    version: str = Field(..., description="Form version")
    trigger_when: Optional[str] = Field(None, description="Trigger condition")
    forms: List[FormItem] = Field(..., description="Array of form items")
    actions: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Form actions")
    modal_type: Optional[str] = Field("AntModalAdapter", description="Modal type")
    tooltip_type: Optional[str] = Field("AntTooltip", description="Tooltip type")
    error_type: Optional[str] = Field("AntErrorMessage", description="Error type")
    localization: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Localization")
    languages: Optional[List[Language]] = Field(default_factory=list, description="Languages")
    default_language: Optional[str] = Field("en-US", description="Default language")

class FormExport(BaseModel):
    """Schema for exporting form to JSON"""
    name: str
    version: str
    trigger_when: Optional[str] = None
    forms: List[Dict[str, Any]]  # Complete forms array as dict
    actions: Dict[str, Any]
    modal_type: str
    tooltip_type: str
    error_type: str
    localization: Dict[str, Any]
    languages: List[Dict[str, Any]]
    default_language: str

    model_config = ConfigDict(from_attributes=True)

# Frontend form structure (from form builder)
class FrontendFormItem(BaseModel):
    """Single form item from frontend form builder"""
    form_id: Optional[str] = Field(None, description="Form ID (optional, will be set automatically)")
    name: str = Field(..., description="Form name")
    defaultLanguage: str = Field(..., alias="defaultLanguage")
    form: FormStructure = Field(..., description="Form structure")
    languages: List[Language] = Field(default_factory=list, description="Supported languages")
    localization: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Localization data")
    modalType: Optional[str] = Field("AntModal", alias="modalType")
    tooltipType: Optional[str] = Field("AntTooltip", alias="tooltipType")
    errorType: Optional[str] = Field("AntErrorMessage", alias="errorType")
    triggerWhen: Optional[Dict[str, Any]] = Field(default_factory=dict, alias="triggerWhen")
    version: str = Field(..., description="Form version")

    model_config = ConfigDict(populate_by_name=True)

class FrontendFormCreate(BaseModel):
    """Schema for creating form from frontend form builder"""
    menu_id: uuid.UUID = Field(..., description="Menu ID this form belongs to")
    access: Union[str, List[str]] = Field(default_factory=list, description="Form access permissions")
    forms: List[FrontendFormItem] = Field(..., description="Array of form items (usually contains 1 item)")

    @field_validator('access')
    @classmethod
    def validate_access(cls, v):
        """Convert string access to list"""
        if isinstance(v, str):
            return [v] if v else []
        elif isinstance(v, list):
            return v
        else:
            return []

    model_config = ConfigDict(populate_by_name=True)