from pydantic import AfterValidator
from typing_extensions import Annotated

from app.core.validations.validation_logic import (
    not_empty,
)

NonEmptyTokenRequired = Annotated[
    str,
    AfterValidator(not_empty("Token")),
]
