from typing import Any, TypeVar

from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

ModelT = TypeVar("ModelT", bound=BaseModel)


class PydanticJSONB(TypeDecorator[ModelT]):
    """JSONB column that validates through a Pydantic model on write and read.

    Writes accept the model or a plain dict; reads always return the model.
    In-place mutation is not tracked: assign a new model to persist changes.
    """

    impl = JSONB
    cache_ok = True

    def __init__(self, model: type[ModelT]) -> None:
        super().__init__()
        self.model = model

    def process_bind_param(self, value: Any, dialect: Dialect) -> dict[str, Any] | None:
        if value is None:
            return None
        return self.model.model_validate(value).model_dump(mode="json")

    def process_result_value(self, value: Any, dialect: Dialect) -> ModelT | None:
        if value is None:
            return None
        return self.model.model_validate(value)
