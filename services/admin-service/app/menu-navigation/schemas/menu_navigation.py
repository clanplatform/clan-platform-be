from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class Badge(BaseModel):
    count: Union[int, str]
    color: str = "blue"


class UserData(BaseModel):
    name: str
    email: str
    avatar: str
    role: str
    status: str = "online"


class ProfileMenuItem(BaseModel):
    key: str
    label: str
    icon: str
    children: List[Any] = Field(default_factory=list)
    type: Optional[str] = None
    badge: Optional[Badge] = None


class ProfileSection(BaseModel):
    type: str = "profile"
    key: str = "profile-section"
    userData: UserData
    menuItems: List[ProfileMenuItem]


class NavigationConfig(BaseModel):
    version: str = "2.1.0"
    lastUpdated: Optional[datetime] = None
    dataHash: Optional[str] = None
    defaultExpandedKeys: List[str] = Field(default_factory=list)
    defaultSelectedKeys: List[str] = Field(default_factory=list)
    theme: str = "light"
    mode: str = "inline"
    collapsible: bool = True
    selectable: bool = True
    multiple: bool = False


class NavigationMenuItem(BaseModel):
    key: str
    label: str
    menu_id: Optional[str] = None  # ✅ UUID from PostgreSQL menus.id (primary key)
    application_id: Optional[str] = None  # UUID of the application this navigation belongs to
    icon: Optional[str] = ""
    description: Optional[str] = None
    badge: Optional[Badge] = None
    sectionTitle: Optional[str] = None
    object_id: Optional[str] = ""  # Object ID for linking to specific resources
    icons: Optional[List[Dict[str, Any]]] = None  # Array of icon objects
    children: List['NavigationMenuItem'] = Field(default_factory=list)
    route: Optional[str] = None
    component: Optional[str] = None
    order_index: int = 0
    level: int = 1
    is_visible: bool = True
    is_active: bool = True
    menu_metadata: Dict[str, Any] = Field(default_factory=dict)


class NavigationStructure(BaseModel):
    mainNavigation: List[NavigationMenuItem]  # Array of navigation items
    profileSection: ProfileSection
    config: NavigationConfig


class NavigationResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    structure: NavigationStructure
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


class NavigationCreate(BaseModel):
    application_id: uuid.UUID
    structure: NavigationStructure


class NavigationUpdate(BaseModel):
    structure: Optional[NavigationStructure] = None
    is_active: Optional[bool] = None


class NavigationImport(BaseModel):
    application_id: uuid.UUID
    structure: NavigationStructure
    overwrite: bool = False


class NavigationExport(BaseModel):
    application_id: uuid.UUID
    include_metadata: bool = True


# Allow recursive reference
NavigationMenuItem.model_rebuild()


def validate_navigation_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a navigation item and ensure all required fields are present.

    Required fields:
    - key: Unique identifier
    - label: Display name
    - icon: Icon class (can be None)
    - description: Description text
    - badge: Badge configuration (can be None)
    - children: Array of child menu items (can be empty [])

    Args:
        item: Dictionary representing a navigation menu item

    Returns:
        Validated dictionary with all required fields

    Raises:
        ValueError: If validation fails
    """
    try:
        # Ensure all required fields are present
        required_fields = ['key', 'label', 'icon', 'description', 'badge', 'children']

        # Set defaults for missing required fields
        if 'icon' not in item:
            item['icon'] = None
        if 'description' not in item:
            item['description'] = f"Manage {item.get('label', 'item').lower()}"
        if 'badge' not in item:
            item['badge'] = None
        if 'children' not in item:
            item['children'] = []

        # Validate using Pydantic model
        validated = NavigationMenuItem(**item)
        result = validated.dict(exclude_none=False, by_alias=False)

        # ✅ Preserve extra fields that are not in the Pydantic model
        # This allows fields like menu_id, application_id, object_id to pass through
        for key, value in item.items():
            if key not in result:
                result[key] = value

        return result
    except Exception as e:
        raise ValueError(f"Navigation item validation failed: {e}")


def create_navigation_item(
    key: str,
    label: str,
    icon: Optional[str] = None,
    description: Optional[str] = None,
    badge: Optional[Dict[str, Any]] = None,
    children: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a validated navigation item with all required fields.

    This helper ensures that every navigation item has all required fields:
    - key: Unique identifier
    - label: Display name
    - icon: Icon class (can be None)
    - description: Description text (auto-generated if not provided)
    - badge: Badge configuration (can be None)
    - children: Child menu items - ARRAY []

    Args:
        key: Unique identifier
        label: Display name
        icon: Icon class (optional)
        description: Description text (optional, auto-generated if not provided)
        badge: Badge configuration (optional)
        children: Child menu items (optional) - ARRAY []
        **kwargs: Additional optional fields (route, sectionTitle, menu_id, application_id, etc.)

    Returns:
        Validated navigation item dictionary

    Example:
        >>> item = create_navigation_item(
        ...     key="domains",
        ...     label="Domains",
        ...     icon=None,
        ...     description="Manage domain configurations",
        ...     badge=None,
        ...     children=[]  # ✅ Use array for children
        ... )
    """
    # ✅ Default children to [] (array) to maintain array structure
    item = {
        "key": key,
        "label": label,
        "icon": icon,
        "description": description or f"Manage {label.lower()}",
        "badge": badge,
        "children": children if children is not None else [],
        **kwargs
    }

    return validate_navigation_item(item)