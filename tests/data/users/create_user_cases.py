from app.core.validations.messages import Msg

# --------------------------------------------------------------------
# 0. THE VALID BASE
# We use this to fill in the missing mandatory fields for creation tests.
# --------------------------------------------------------------------
VALID_BASE = {
    "username": "valid_user",
    "email": "valid@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "password": "ValidPassword1!",
}

USERNAME_CREATION_CASES = [
    {
        "id": "username_empty",
        "data": {**VALID_BASE, "username": ""},
        "expected_errors": {"username": [Msg.FIELD_EMPTY.format(field="Username")]},
    },
    {
        "id": "username_too_short",
        "data": {**VALID_BASE, "username": "ab"},
        "expected_errors": {
            "username": [Msg.MIN_LENGTH.format(field="Username", min=3)]
        },
    },
    {
        "id": "username_no_alpha",
        "data": {**VALID_BASE, "username": "12345"},
        "expected_errors": {"username": [Msg.USERNAME_NO_ALPHA]},
    },
    {
        "id": "username_invalid_chars",
        "data": {**VALID_BASE, "username": "invalid@name"},
        "expected_errors": {"username": [Msg.USERNAME_INVALID_CHARS]},
    },
    {
        "id": "username_consecutive_dots",
        "data": {**VALID_BASE, "username": "user..name"},
        "expected_errors": {"username": [Msg.USERNAME_CONSECUTIVE_DOTS]},
    },
    {
        "id": "username_trailing_dot",
        "data": {**VALID_BASE, "username": "username."},
        "expected_errors": {"username": [Msg.USERNAME_TRAILING_DOT]},
    },
]


PASSWORD_CREATION_CASES = [
    {
        "id": "password_empty",
        "data": {**VALID_BASE, "password": ""},
        "expected_errors": {"password": [Msg.FIELD_EMPTY.format(field="Password")]},
    },
    {
        "id": "password_too_short",
        "data": {**VALID_BASE, "password": "Pass1!"},
        "expected_errors": {
            "password": [Msg.MIN_LENGTH.format(field="Password", min=8)]
        },
    },
    {
        "id": "password_no_digit",
        "data": {**VALID_BASE, "password": "Password!"},
        "expected_errors": {"password": [Msg.PASSWORD_NO_DIGIT]},
    },
    {
        "id": "password_no_lower",
        "data": {**VALID_BASE, "password": "PASSWORD1!"},
        "expected_errors": {"password": [Msg.PASSWORD_NO_LOWER]},
    },
    {
        "id": "password_no_upper",
        "data": {**VALID_BASE, "password": "password1!"},
        "expected_errors": {"password": [Msg.PASSWORD_NO_UPPER]},
    },
    {
        "id": "password_no_symbol",
        "data": {**VALID_BASE, "password": "Password123"},
        "expected_errors": {"password": [Msg.PASSWORD_NO_SYMBOL]},
    },
    {
        "id": "password_chaos",
        "data": {**VALID_BASE, "password": "tinypooks"},
        "expected_errors": {
            "password": [
                Msg.PASSWORD_NO_UPPER,
                Msg.PASSWORD_NO_DIGIT,
                Msg.PASSWORD_NO_SYMBOL,
            ]
        },
    },
]

FIRST_NAME_CREATION_CASES = [
    {
        "id": "first_name_empty",
        "data": {**VALID_BASE, "first_name": ""},
        "expected_errors": {"first_name": [Msg.FIELD_EMPTY.format(field="First name")]},
    },
    {
        "id": "first_name_too_short",
        "data": {**VALID_BASE, "first_name": "J"},
        "expected_errors": {
            "first_name": [Msg.MIN_LENGTH.format(field="First name", min=2)]
        },
    },
    {
        "id": "first_name_invalid_chars",
        "data": {**VALID_BASE, "first_name": "John123"},
        "expected_errors": {
            "first_name": [Msg.NAME_INVALID_CHARS.format(field="First name")]
        },
    },
]


EMAIL_CREATION_CASES = [
    {
        "id": "email_empty",
        "data": {**VALID_BASE, "email": ""},
        "expected_errors": {"email": Msg.EMAIL_INVALID},
    },
    {
        "id": "email_missing_at",
        "data": {**VALID_BASE, "email": "john.doe.com"},
        "expected_errors": {"email": Msg.EMAIL_INVALID},
    },
    {
        "id": "email_missing_domain",
        "data": {**VALID_BASE, "email": "john@"},
        "expected_errors": {"email": Msg.EMAIL_INVALID},
    },
]

LAST_NAME_CREATION_CASES = [
    {
        "id": "last_name_too_short",
        "data": {**VALID_BASE, "last_name": "D"},
        "expected_errors": {
            "last_name": [Msg.MIN_LENGTH.format(field="Last name", min=2)]
        },
    },
    {
        "id": "last_name_invalid_chars",
        "data": {**VALID_BASE, "last_name": "Doe123"},
        "expected_errors": {
            "last_name": [Msg.NAME_INVALID_CHARS.format(field="Last name")]
        },
    },
]


CHAOS_CREATION_CASES = [
    {
        "id": "all_fields_invalid",
        "data": {
            "username": "a",  # Short
            "email": "not-an-email",  # Invalid Email
            "first_name": "123",  # Invalid Name
            "last_name": "LST.a",  # Invalid Name
            "password": "tinypooks",  # Weak Password
        },
        "expected_errors": {
            "username": [Msg.MIN_LENGTH.format(field="Username", min=3)],
            "email": Msg.EMAIL_INVALID,
            "first_name": [Msg.NAME_INVALID_CHARS.format(field="First name")],
            "last_name": [Msg.NAME_INVALID_CHARS.format(field="Last name")],
            "password": [
                Msg.PASSWORD_NO_UPPER,
                Msg.PASSWORD_NO_DIGIT,
                Msg.PASSWORD_NO_SYMBOL,
            ],
        },
    },
]


# --------------------------------------------------------------------
# 4. EXPORT FINAL LIST
# --------------------------------------------------------------------
USER_CREATION_CASES = (
    USERNAME_CREATION_CASES
    + FIRST_NAME_CREATION_CASES
    + LAST_NAME_CREATION_CASES
    + PASSWORD_CREATION_CASES
    + EMAIL_CREATION_CASES
    + CHAOS_CREATION_CASES
)
