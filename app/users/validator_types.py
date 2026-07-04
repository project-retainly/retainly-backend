from typing import Optional

from pydantic import AfterValidator, WrapValidator
from typing_extensions import Annotated

from app.core.validations.validation_logic import (
    human_name,
    length,
    not_empty,
    password_rules,
    reject_null,
    username_rules,
)

# ---------- USERNAME ----------

UsernameRequired = Annotated[
    str,
    AfterValidator(not_empty("Username")),
    AfterValidator(length("Username", 3, 30)),
    AfterValidator(username_rules()),
]

UsernameOptional = Optional[UsernameRequired]


# ---------- FIRST NAME ----------

FirstNameRequired = Annotated[
    str,
    AfterValidator(not_empty("First name")),
    AfterValidator(length("First name", 2, 70)),
    AfterValidator(human_name("First name")),
]

FirstNameOptional = Annotated[
    str | None,  # Updating is optional, but if provided, must be valid
    WrapValidator(reject_null("First name")),
    AfterValidator(not_empty("First name")),
    AfterValidator(length("First name", 2, 70)),
    AfterValidator(human_name("First name")),
]


# ---------- LAST NAME ----------

LastNameOptionalAllowNull = Optional[
    Annotated[
        str,
        AfterValidator(not_empty("Last name")),
        AfterValidator(length("Last name", 2, 70)),
        AfterValidator(human_name("Last name")),
    ]
]


# ---------- PASSWORD ----------

PasswordRequired = Annotated[
    str,
    WrapValidator(reject_null("Password")),
    AfterValidator(not_empty("Password")),
    AfterValidator(length("Password", 8, 100)),
    AfterValidator(password_rules()),
]
