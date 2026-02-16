"""
SQLAlchemy Declarative Base

Provides the base class for all ORM models.
Centralizes metadata for schema generation and migrations.
"""

from sqlalchemy.orm import declarative_base

# Create the declarative base
# All ORM models should inherit from this Base
Base = declarative_base()


def import_all_models():
    """
    Import all models to register them with Base.metadata.
    
    This function must be called before create_all() or drop_all()
    to ensure all models are registered with the metadata.
    
    Models are imported from their respective domain modules:
    - app.interview.models
    - app.evaluation.models
    - app.auth.models (once implemented)
    - app.coding.models (once implemented)
    - app.audio.models (once implemented)
    
    Note: This is called automatically by engine initialization.
    """
    # TODO: Import models as they are implemented
    # Example:
    # from app.interview.models import InterviewSubmission, InterviewExchange
    # from app.evaluation.models import Evaluation, EvaluationDimensionScore
    # from app.auth.models import User, Role
    # from app.coding.models import CodeSubmission, TestCase
    # from app.audio.models import AudioRecording
    pass


def get_table_names() -> list[str]:
    """
    Get list of all registered table names.
    
    Returns:
        List of table names registered in Base.metadata
    """
    return [table.name for table in Base.metadata.sorted_tables]
