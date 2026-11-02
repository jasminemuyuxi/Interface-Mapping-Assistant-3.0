"""Define shared ORM metadata without loading database configuration."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Provide shared metadata for all ORM models.

    Check constraints must have an explicit semantic name, such as
    ``positive_quantity``, which the convention prefixes with the table name.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
