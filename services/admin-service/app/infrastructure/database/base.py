"""
Database base module - defines the SQLAlchemy declarative base
"""
from sqlalchemy.ext.declarative import declarative_base

# Create the declarative base for all models
Base = declarative_base()
