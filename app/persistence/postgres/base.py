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
    # Import models to register them with Base.metadata
    import app.auth.persistence.models  # noqa: F401
    import app.admin.persistence.models  # noqa: F401
    import app.ai.prompts.models  # noqa: F401
    import app.coding.persistence.models  # noqa: F401
    import app.question.generation.persistence.models  # noqa: F401
    import app.question.persistence.models  # noqa: F401
    import app.question.selection.persistence.models  # noqa: F401
    import app.interview.session.persistence.models  # noqa: F401
    import app.proctoring.persistence.models  # noqa: F401
    import app.evaluation.persistence.models  # noqa: F401
    import app.audio.persistence.models  # noqa: F401
    pass


def get_table_names() -> list[str]:
    """
    Get list of all registered table names.
    
    Returns:
        List of table names registered in Base.metadata
    """
    return [table.name for table in Base.metadata.sorted_tables]
