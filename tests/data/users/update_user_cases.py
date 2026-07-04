from app.core.validations.messages import Msg

# --------------------------------------------------------------------
# 1. USERNAME VALIDATION CASES
# Logic: Strip -> Check Empty (Blocking) -> Lowercase -> Check (Length, Regex, Dots)
# --------------------------------------------------------------------
USERNAME_UPDATE_CASES = [
    # --- BLOCKING ERROR (Stops further checks) ---
    {
        "id": "username_empty",
        "data": {"username": ""},
        "expected_errors": {"username": [Msg.FIELD_EMPTY.format(field="Username")]},
    },
    {
        "id": "username_whitespace_only",
        "data": {"username": "   "},
        "expected_errors": {"username": [Msg.FIELD_EMPTY.format(field="Username")]},
    },
    # --- LENGTH CHECKS (Min 3, Max 30) ---
    {
        "id": "username_too_short_2chars",
        "data": {"username": "ab"},
        "expected_errors": {
            "username": [Msg.MIN_LENGTH.format(field="Username", min=3)]
        },
    },
    {
        "id": "username_too_long_31chars",
        "data": {"username": "a" * 31},
        "expected_errors": {
            "username": [Msg.MAX_LENGTH.format(field="Username", max=30)]
        },
    },
    # --- REGEX CHECK (^[a-z_][a-z0-9_.]*$) ---
    # Must start with letter or underscore. Can contain alphanumeric, dot, underscore.
    {
        "id": "username_start_with_number",
        "data": {"username": "9user"},
        "expected_errors": {"username": [Msg.USERNAME_INVALID_CHARS]},
    },
    {
        "id": "username_start_with_dot",
        "data": {"username": ".user"},
        "expected_errors": {"username": [Msg.USERNAME_INVALID_CHARS]},
    },
    {
        "id": "username_invalid_chars_space",
        "data": {"username": "user name"},
        "expected_errors": {"username": [Msg.USERNAME_INVALID_CHARS]},
    },
    {
        "id": "username_invalid_chars_symbol",
        "data": {"username": "user$name"},
        "expected_errors": {"username": [Msg.USERNAME_INVALID_CHARS]},
    },
    {
        "id": "username_invalid_chars_dash",
        "data": {"username": "user-name"},  # Dash is disallowed in your regex
        "expected_errors": {"username": [Msg.USERNAME_INVALID_CHARS]},
    },
    # --- DOT CHECKS (Consecutive, Trailing) ---
    {
        "id": "username_consecutive_dots",
        "data": {"username": "user..name"},
        "expected_errors": {"username": [Msg.USERNAME_CONSECUTIVE_DOTS]},
    },
    {
        "id": "username_trailing_dot",
        "data": {"username": "username."},
        "expected_errors": {"username": [Msg.USERNAME_TRAILING_DOT]},
    },
    # --- MULTIPLE ERRORS (The Bucket Logic) ---
    {
        "id": "username_trailing_dot_and_consecutive",
        "data": {"username": "user..name."},
        "expected_errors": {
            "username": [
                Msg.USERNAME_CONSECUTIVE_DOTS,  # contains ..
                Msg.USERNAME_TRAILING_DOT,  # ends with .
            ]
        },
    },
    {
        "id": "username_chaos_combo",
        "data": {"username": ".u.."},
        "expected_errors": {
            "username": [
                Msg.USERNAME_INVALID_CHARS,  # starts with .
                Msg.USERNAME_CONSECUTIVE_DOTS,  # contains ..
                Msg.USERNAME_TRAILING_DOT,  # ends with .
            ]
        },
    },
    {
        "id": "username_with_sql_injection",
        "data": {"username": "admin'; DROP TABLE users; --"},
        "expected_errors": {
            "username": [
                Msg.USERNAME_INVALID_CHARS,  # starts with .
            ]
        },
    },
]

# --------------------------------------------------------------------
# 2. NAME VALIDATION CASES (First & Last)
# Logic: Strip -> Check Empty -> Check (Length, Regex) -> Title Case
# Regex: ^[a-zA-Z\s\-']+$ (Letters, spaces, hyphens, apostrophes)
# --------------------------------------------------------------------
NAME_UPDATE_CASES = [
    # --- BLOCKING ERROR ---
    {
        "id": "firstname_empty",
        "data": {"first_name": ""},
        "expected_errors": {"first_name": [Msg.FIELD_EMPTY.format(field="First name")]},
    },
    {
        "id": "lastname_whitespace",
        "data": {"last_name": "   "},
        "expected_errors": {"last_name": [Msg.FIELD_EMPTY.format(field="Last name")]},
    },
    # --- LENGTH CHECKS (Min 2, Max 50) ---
    {
        "id": "firstname_too_short",
        "data": {"first_name": "A"},
        "expected_errors": {
            "first_name": [Msg.MIN_LENGTH.format(field="First name", min=2)]
        },
    },
    {
        "id": "lastname_too_long",
        "data": {"last_name": "A" * 71},
        "expected_errors": {
            "last_name": [Msg.MAX_LENGTH.format(field="Last name", max=70)]
        },
    },
    # --- REGEX CHECKS ---
    {
        "id": "firstname_numbers",
        "data": {"first_name": "John123"},
        "expected_errors": {
            "first_name": [Msg.NAME_INVALID_CHARS.format(field="First name")]
        },
    },
    {
        "id": "lastname_symbols",
        "data": {"last_name": "Doe@"},
        "expected_errors": {
            "last_name": [Msg.NAME_INVALID_CHARS.format(field="Last name")]
        },
    },
    {
        "id": "firstname_underscore",
        "data": {"first_name": "John_Doe"},
        "expected_errors": {
            "first_name": [Msg.NAME_INVALID_CHARS.format(field="First name")]
        },
    },
]

# --------------------------------------------------------------------
# 3. COMBINED CASES (Multiple fields failing at once)
# --------------------------------------------------------------------
COMBINED_UPDATE_CASES = [
    {
        "id": "all_fields_invalid",
        "data": {
            "username": "u.",  # Too short
            "first_name": "A",  # Too short
            "last_name": "Doe1",  # Invalid chars
        },
        "expected_errors": {
            "username": [
                Msg.MIN_LENGTH.format(field="Username", min=3),
            ],
            "first_name": [Msg.MIN_LENGTH.format(field="First name", min=2)],
            "last_name": [Msg.NAME_INVALID_CHARS.format(field="Last name")],
        },
    },
    {
        "id": "xss_in_first_name_and_last_name",
        "data": {
            "first_name": "<script>alert('XSS')</script>",
            "last_name": "<script>alert('XSS')</script>",
        },
        "expected_errors": {
            "first_name": [Msg.NAME_INVALID_CHARS.format(field="First name")],
            "last_name": [Msg.NAME_INVALID_CHARS.format(field="Last name")],
        },
    },
]

# EXPORT EVERYTHING
ALL_UPDATE_CASES = USERNAME_UPDATE_CASES + NAME_UPDATE_CASES + COMBINED_UPDATE_CASES
