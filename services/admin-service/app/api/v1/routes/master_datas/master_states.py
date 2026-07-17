from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, Request
from sqlalchemy.orm import Session
import math
import uuid

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.master_datas.services.master_states import MasterStateService
from app.master_datas.exceptions import StateNotFoundError
from app.master_datas.schemas.master_states import (
    MasterStateCreate,
    MasterStateUpdate,
    MasterStateResponse,
    MasterStateListResponse,
)
from app.infrastructure.audit_helpers import (
    RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id,
)
from app.infrastructure.audit_tenant import fire_audit_log

router = APIRouter()


def _audit(request: Request, db: Session, current_user, action: str, **kwargs) -> None:
    """Fire an audit log enriched with the acting user's org context. Never fatal."""
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action=action,
            object_type="MasterState",
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            **kwargs,
        )
    except Exception:
        pass


@router.post(
    "/",
    response_model=MasterStateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a state",
    description="Add a state/province under a country. `state_name` and `state_code` must be "
                "unique within that country, but may repeat across different countries.",
    responses={
        404: {"description": "The referenced country does not exist"},
        409: {"description": "This country already has a state with that name or code"},
    },
)
async def create_state(
    request: Request,
    state_data: MasterStateCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    state = MasterStateService.create_state(db, state_data)
    _audit(
        request, db, current_user, "CREATE",
        object_id=str(state.id),
        risk_score=RISK_SCORE["CREATE"],
        new_values={"state_name": state.state_name, "country_id": str(state.country_id)},
    )
    return state


@router.get(
    "/",
    response_model=MasterStateListResponse,
    summary="List states",
    description="Paginated state list with optional country/active filters, search and sorting.",
)
async def get_states(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="1-based page number"),
    size: int = Query(50, ge=1, le=250, description="Rows per page"),
    country_id: Optional[uuid.UUID] = Query(None, description="Filter by country"),
    is_active: Optional[bool] = Query(None, description="Filter by active flag"),
    search: Optional[str] = Query(None, description="Match state name, code or capital"),
    sort_by: str = Query("display_order", description="Sort column"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort direction"),
):
    states, total = MasterStateService.get_states(
        db=db,
        skip=(page - 1) * size,
        limit=size,
        country_id=country_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return MasterStateListResponse(
        states=states,
        total=total,
        page=page,
        size=size,
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


# Registered before /{state_id} so this literal path wins the match.
@router.get(
    "/by-country/{country_id}",
    response_model=List[MasterStateResponse],
    summary="Get all states for a country",
    description="Unpaginated list ordered by display_order — intended for cascading country/state pickers.",
    responses={404: {"description": "The referenced country does not exist"}},
)
async def get_states_by_country(
    request: Request,
    country_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    is_active: Optional[bool] = Query(None, description="Filter by active flag"),
):
    return MasterStateService.get_states_by_country(db, country_id, is_active=is_active)


@router.get(
    "/{state_id}",
    response_model=MasterStateResponse,
    summary="Get a state by ID",
    responses={404: {"description": "State not found"}},
)
async def get_state(
    request: Request,
    state_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    state = MasterStateService.get_state(db, state_id)
    if not state:
        raise StateNotFoundError(str(state_id))
    return state


@router.put(
    "/{state_id}",
    response_model=MasterStateResponse,
    summary="Update a state",
    description="Partial update — only the fields present in the body are changed. "
                "Supplying `country_id` moves the state to another country.",
    responses={
        404: {"description": "State (or the target country) not found"},
        409: {"description": "The target country already has a state with that name or code"},
    },
)
async def update_state(
    request: Request,
    state_id: uuid.UUID,
    state_data: MasterStateUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    state = MasterStateService.update_state(db, state_id, state_data)
    _audit(
        request, db, current_user, "UPDATE",
        object_id=str(state_id),
        risk_score=RISK_SCORE["UPDATE"],
        new_values=state_data.model_dump(exclude_unset=True, mode="json"),
    )
    return state


@router.delete(
    "/{state_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a state",
    description="Permanently removes the state. Use `is_active=false` via PUT to retire one instead.",
    responses={404: {"description": "State not found"}},
)
async def delete_state(
    request: Request,
    state_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    state = MasterStateService.delete_state(db, state_id)
    _audit(
        request, db, current_user, "DELETE",
        object_id=str(state_id),
        risk_score=RISK_SCORE["DELETE"],
        old_values={"state_name": state.state_name, "country_id": str(state.country_id)},
    )
