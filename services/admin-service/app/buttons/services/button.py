from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from app.buttons.models.button import Button
from app.buttons.schemas.button import ButtonCreate, ButtonUpdate
from app.infrastructure.audit_tenant import fire_audit_log


class ButtonService:

    @staticmethod
    def create_button(db: Session, button_data: ButtonCreate, created_by: Optional[str] = None) -> Button:
        db_button = Button(**button_data.model_dump(), created_by=created_by)
        db.add(db_button)
        db.commit()
        db.refresh(db_button)
        fire_audit_log(
            action="CREATE", object_type="Button",
            object_id=str(db_button.id),
            new_values={"name": db_button.name, "menu_id": str(db_button.menu_id)},
        )
        return db_button

    @staticmethod
    def get_button(db: Session, button_id: str) -> Optional[Button]:
        return db.query(Button).filter(
            and_(Button.id == button_id, Button.is_deleted == False)
        ).first()

    @staticmethod
    def get_buttons(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        menu_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "order_index",
        sort_order: str = "asc",
    ) -> tuple[List[Button], int]:
        query = db.query(Button).filter(Button.is_deleted == False)

        if menu_id:
            query = query.filter(Button.menu_id == menu_id)
        if is_active is not None:
            query = query.filter(Button.is_active == is_active)
        if search:
            query = query.filter(
                or_(
                    Button.name.ilike(f"%{search}%"),
                    Button.label.ilike(f"%{search}%"),
                    Button.key.ilike(f"%{search}%"),
                )
            )

        if hasattr(Button, sort_by):
            col = getattr(Button, sort_by)
            query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))

        total = query.count()
        buttons = query.offset(skip).limit(limit).all()
        return buttons, total

    @staticmethod
    def get_buttons_by_menu(db: Session, menu_id: str, is_active: Optional[bool] = None) -> List[Button]:
        query = db.query(Button).filter(
            and_(Button.menu_id == menu_id, Button.is_deleted == False)
        )
        if is_active is not None:
            query = query.filter(Button.is_active == is_active)
        return query.order_by(Button.order_index).all()

    @staticmethod
    def update_button(
        db: Session, button_id: str, button_data: ButtonUpdate, updated_by: Optional[str] = None
    ) -> Optional[Button]:
        db_button = ButtonService.get_button(db, button_id)
        if not db_button:
            return None

        update_data = button_data.model_dump(exclude_unset=True)
        if updated_by:
            update_data["updated_by"] = updated_by

        for field, value in update_data.items():
            setattr(db_button, field, value)

        db.commit()
        db.refresh(db_button)
        fire_audit_log(
            action="UPDATE", object_type="Button",
            object_id=str(button_id),
            new_values=update_data,
        )
        return db_button

    @staticmethod
    def delete_button(db: Session, button_id: str, deleted_by: Optional[str] = None) -> bool:
        db_button = ButtonService.get_button(db, button_id)
        if not db_button:
            return False

        db_button.is_deleted = True
        db_button.is_active = False
        if deleted_by:
            db_button.updated_by = deleted_by

        db.commit()
        fire_audit_log(
            action="DELETE", object_type="Button",
            object_id=str(button_id),
            old_values={"is_deleted": False}, new_values={"is_deleted": True},
        )
        return True
