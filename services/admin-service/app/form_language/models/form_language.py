from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Sequence
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.infrastructure.database.base import Base
import uuid


class FormLanguage(Base):
    """
    Form language translations table.
    Stores translations for form fields, labels, placeholders, and error messages.
    """
    __tablename__ = "form_languages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sino = Column(Integer, Sequence('form_languages_sino_seq'), unique=True, nullable=False)
    lang_code = Column(String(10), nullable=False, index=True)
    language = Column(String(100), nullable=False)
    app_form_entity_type = Column(String(100), nullable=False, index=True)  # 'form', 'field', 'section'
    app_form_entity_id = Column(UUID(as_uuid=True), ForeignKey('forms.id', ondelete='CASCADE'), nullable=False, index=True)
    translated_name = Column(String(255), nullable=True)
    type = Column(String(100), nullable=True)  # 'label', 'placeholder', 'help_text', 'error_message'
    value = Column(Text, nullable=True)
    key = Column(String(255), nullable=True, index=True)
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to forms table
    form = relationship("Form", backref="form_languages")

    def __repr__(self):
        return f"<FormLanguage(id={self.id}, sino={self.sino}, lang_code={self.lang_code}, language={self.language}, entity_type={self.app_form_entity_type}, entity_id={self.app_form_entity_id}, translated_name={self.translated_name})>"
