from enum import StrEnum

from sqlalchemy import Enum


def pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Native Postgres enum that stores the lowercase values, not the member names."""
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )
