from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for future SQLAlchemy models; no business tables are defined in this phase."""
