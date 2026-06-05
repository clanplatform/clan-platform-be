from sqlalchemy import Column, String, DateTime, Integer, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class MenuLanguage(Base):
    __tablename__ = "menu_languages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sino = Column(Integer, autoincrement=True, unique=True, nullable=False, server_default=text("nextval('menu_languages_sino_seq'::regclass)"))
    lang_code = Column(String(10), nullable=False, index=True)
    language = Column(String(100), nullable=False)  # Language name (e.g., 'Spanish', 'Tamil')
    translated_name = Column(String(255), nullable=False, index=True)  # The actual translated text
    app_menu_entity_type = Column(String(50), nullable=False, index=True)  # 'application', 'module', 'menu'
    app_menu_entity_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<MenuLanguage(id={self.id}, sino={self.sino}, lang_code={self.lang_code}, language={self.language}, translated_name={self.translated_name}, entity_type={self.app_menu_entity_type}, entity_id={self.app_menu_entity_id})>"
