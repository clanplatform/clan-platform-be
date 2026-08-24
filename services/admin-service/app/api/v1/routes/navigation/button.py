from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, Request
from sqlalchemy.orm import Session
import math

from app.infrastructure.database.session import get_tenant_db as get_db
from app.core.security import get_current_user
from app.buttons.services.button import ButtonService
from app.buttons.schemas.button import ButtonCreate, ButtonUpdate, ButtonResponse, ButtonListResponse
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.user_role.services.user_role import UserRoleService

router = APIRouter()


def _user_permission_context(db: Session, current_user: dict):
    """Resolve the current user's role-based access context (see
    UserRoleService.get_user_permission_context) so buttons can be scoped to
    the same menu/form/button permissions the dashboard nav is scoped to."""
    user_id_str = get_user_id(current_user)
    try:
        user_uuid = UUID(user_id_str) if user_id_str else None
    except ValueError:
        user_uuid = None
    return UserRoleService.get_user_permission_context(db, user_uuid)


@router.post(
    "/",
    response_model=ButtonResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new button",
)
async def create_button(
    request: Request,
    button_data: ButtonCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        button = ButtonService.create_button(db, button_data, created_by=get_user_id(current_user))
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE", object_type="Button", object_id=str(button.id),
                user_id=get_user_id(current_user), tenant_id=tenant_id_audit, entity_id=entity_id_audit,
                session_id=get_session_id(current_user), ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["CREATE"],
                new_values={"name": button.name, "menu_id": str(button.menu_id)},
            )
        except Exception:
            pass
        return button
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create button: {str(e)}")


@router.get(
    "/",
    response_model=ButtonListResponse,
    summary="List buttons with filtering and pagination",
)
async def get_buttons(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    menu_id: Optional[str] = Query(None, description="Filter by menu ID"),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    sort_by: str = Query("order_index"),
    sort_order: str = Query("asc", regex="^(asc|desc)$"),
):
    skip = (page - 1) * size
    try:
        buttons, total = ButtonService.get_buttons(
            db=db, skip=skip, limit=size, menu_id=menu_id,
            is_active=is_active, search=search, sort_by=sort_by, sort_order=sort_order,
        )
        # Scope down to what the user's role permissions actually grant
        # (dashboard should only ever show permissioned buttons). Note this
        # filters after pagination, so a page can come back smaller than
        # `size` for a restricted role — acceptable here since button lists
        # are small and this mirrors the existing menu-permission filtering.
        context = _user_permission_context(db, current_user)
        if UserRoleService.should_filter(context, "button"):
            buttons = [b for b in buttons if str(b.id) in context["button_ids"]]
        return ButtonListResponse(
            buttons=buttons, total=total, page=page, size=size,
            total_pages=math.ceil(total / size) if total > 0 else 0,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve buttons: {str(e)}")


@router.get(
    "/menu/{menu_id}",
    response_model=List[ButtonResponse],
    summary="Get all buttons for a menu",
)
async def get_buttons_by_menu(
    request: Request,
    menu_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    is_active: Optional[bool] = Query(None),
):
    try:
        buttons = ButtonService.get_buttons_by_menu(db, menu_id, is_active)
        # Scope down to what the user's role permissions actually grant
        # (dashboard should only ever show permissioned buttons).
        context = _user_permission_context(db, current_user)
        if UserRoleService.should_filter(context, "button"):
            buttons = [b for b in buttons if str(b.id) in context["button_ids"]]
        return buttons
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve buttons: {str(e)}")


@router.get(
    "/{button_id}",
    response_model=ButtonResponse,
    summary="Get a button by ID",
)
async def get_button(
    request: Request,
    button_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    button = ButtonService.get_button(db, button_id)
    if not button:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Button {button_id} not found")
    return button


@router.put(
    "/{button_id}",
    response_model=ButtonResponse,
    summary="Update a button",
)
async def update_button(
    request: Request,
    button_id: str,
    button_data: ButtonUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not ButtonService.get_button(db, button_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Button {button_id} not found")
    try:
        updated = ButtonService.update_button(db, button_id, button_data, updated_by=get_user_id(current_user))
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE", object_type="Button", object_id=str(button_id),
                user_id=get_user_id(current_user), tenant_id=tenant_id_audit, entity_id=entity_id_audit,
                session_id=get_session_id(current_user), ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["UPDATE"],
            )
        except Exception:
            pass
        return updated
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update button: {str(e)}")


@router.delete(
    "/{button_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a button",
)
async def delete_button(
    request: Request,
    button_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    success = ButtonService.delete_button(db, button_id, deleted_by=get_user_id(current_user))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Button {button_id} not found")
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE", object_type="Button", object_id=str(button_id),
            user_id=get_user_id(current_user), tenant_id=tenant_id_audit, entity_id=entity_id_audit,
            session_id=get_session_id(current_user), ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"), risk_score=RISK_SCORE["DELETE"],
        )
    except Exception:
        pass
