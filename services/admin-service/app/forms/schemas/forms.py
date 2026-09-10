from typing import Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from datetime import datetime
import uuid

# Component access permissions
class ComponentAccess(BaseModel):
    """Access permissions for form components"""
    read: bool = Field(True, description="Can read/view the component")
    write: bool = Field(True, description="Can edit/modify the component")
    disable: bool = Field(False, description="Component is disabled")


# The form-builder's own wire vocabulary for props.access.value: [] (Default)
# / read / write / hidden — same vocabulary the role field-permission tree
# uses (see app.user_role.schemas.user_role.FIELD_ACCESS_VALUES). This is
# DIFFERENT from the definition-level `access` field's vocabulary (read/
# write/disable) that app.core.access.cascade_access resolves — 'hidden'
# means the same thing as 'disable' there (see _to_definition_access below,
# mirroring app.core.access._FIELD_TO_TREE_ACCESS).
FIELD_ACCESS_VALUES = {"read", "write", "hidden", "disable"}


class AccessProp(BaseModel):
    """Form-builder prop wrapper for `props.access` — every prop is `{value: ...}`."""
    value: List[str] = Field(
        default_factory=list,
        description="Access permissions: [] (Default) / ['read'] / ['write'] / ['hidden']",
        json_schema_extra={"example": ["read"]},
    )

    @field_validator('value', mode='before')
    @classmethod
    def _normalize_value(cls, v):
        """Lower-case/strip and silently drop unknown tokens — nested
        component access is free-form JSON and must never 500 a form save
        (same lenient philosophy as app.core.access.coerce_access)."""
        if isinstance(v, str):
            v = [v] if v else []
        toks = [str(t).strip().lower() for t in (v or [])]
        return [t for t in toks if t in FIELD_ACCESS_VALUES]


class LabelProp(BaseModel):
    """Form-builder prop wrapper for `props.label` — every prop is `{value: ...}`."""
    value: Optional[str] = Field(None, description="Display label text", json_schema_extra={"example": "Code"})


class ComponentSchema(BaseModel):
    """Form-builder validation schema for a component (form-builder shape:
    {type, validations, autoValidate})."""
    type: Optional[str] = Field(None, description="Field data type", json_schema_extra={"example": "string"})
    validations: List[Any] = Field(default_factory=list, description="Validation rules")
    autoValidate: bool = Field(False, description="Whether to auto-validate on change")


class ComponentProps(BaseModel):
    """A component's props (form-builder convention: every prop is `{value: ...}`).

    `access` and `label` are the well-known props surfaced explicitly; any
    other component-specific prop (placeholder, options, format, ...) passes
    through untouched via extra='allow'.
    """
    access: Optional[AccessProp] = Field(None, description="Field-level access — see FormComponent.access")
    label: Optional[LabelProp] = Field(None, description="Display label")

    model_config = ConfigDict(extra="allow")


def _extract_node_access(data: dict):
    """A form-component node's access, preferring the form-builder's own wire
    convention `props.access.value` (every prop is `{value: ...}` — same
    convention used for role form permissions, see
    app.user_role.schemas.user_role.RoleFormComponentTree), and falling back
    to a top-level `access` key so already-stored / older payloads that only
    ever set it there keep working. Returns None when neither is set (leaves
    the field's own default in place)."""
    props = data.get("props")
    if isinstance(props, dict) and "access" in props:
        ap = props["access"]
        found = ap.get("value") if isinstance(ap, dict) else ap
        if found is not None:
            return found
    return data.get("access")


def _to_definition_access(value):
    """Map the form-builder's props.access.value vocabulary (read/write/
    hidden) onto the definition-level `access` field's vocabulary (read/
    write/disable) that app.core.access.cascade_access understands — 'hidden'
    means the same thing as 'disable' there. Same mapping as
    app.core.access._FIELD_TO_TREE_ACCESS. Without this, a component
    authored as 'hidden' would silently vanish (cascade_access's
    coerce_access drops any token outside read/write/disable) instead of
    behaving like a disabled component."""
    if isinstance(value, str):
        value = [value] if value else []
    return ["disable" if str(t).strip().lower() == "hidden" else t for t in (value or [])]


# Form component structure
class FormComponent(BaseModel):
    """Base form component structure - simplified"""
    key: str = Field(..., description="Unique component key")
    type: str = Field(..., description="Component type (e.g., AntInput, AntButton)")
    access: Union[str, List[str]] = Field(
        default_factory=list,
        description="Access permissions array — resolved from props.access.value "
                    "(form-builder convention) or a top-level access key",
    )
    props: ComponentProps = Field(default_factory=ComponentProps, description="Component properties")
    schema: Optional[ComponentSchema] = Field(
        default=None,
        description="Component validation schema (form-builder shape: {type, validations, autoValidate})",
    )
    tooltipProps: Dict[str, Any] = Field(default_factory=dict, description="Tooltip properties — accepted, not used")
    children: List["FormComponent"] = Field(default_factory=list, description="Child components")

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _normalize_access(cls, data):
        """Surface props.access.value to the top-level `access` field before
        validation, so callers that only ever set access via the form-builder
        prop (not the legacy top-level key) still get a resolved access list —
        this is what app.core.access.cascade_access, the forms JSONB storage
        and get_forms_with_access_level all read. 'hidden' is mapped to
        'disable' for this top-level field (see _to_definition_access) —
        props.access.value itself is left as authored (echoed back via
        ComponentProps/AccessProp)."""
        if isinstance(data, dict):
            extracted = _extract_node_access(data)
            if extracted is not None:
                data = {**data, "access": _to_definition_access(extracted)}
        return data

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


FormComponent.model_rebuild()

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
    props: ComponentProps = Field(default_factory=ComponentProps, description="Form properties")
    access: Union[str, List[str]] = Field(
        default_factory=list,
        description="Form-level access permissions — resolved from props.access.value "
                    "(form-builder convention) or a top-level access key",
    )
    tooltipProps: Dict[str, Any] = Field(default_factory=dict, description="Tooltip properties — accepted, not used")
    children: List[FormComponent] = Field(default_factory=list, description="Form components")

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _normalize_access(cls, data):
        """Same props.access.value-preferring normalization as FormComponent
        (see _extract_node_access / _to_definition_access) applied to the
        form root node."""
        if isinstance(data, dict):
            extracted = _extract_node_access(data)
            if extracted is not None:
                data = {**data, "access": _to_definition_access(extracted)}
        return data

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