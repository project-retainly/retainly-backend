class Msg:
    # Generic
    EMAIL_INVALID = "Invalid email."

    FIELD_NULL = "{field} cannot be null."
    FIELD_EMPTY = "{field} cannot be empty."
    FIELD_REQUIRED = "{field} is required."
    TYPE_INVALID = "{field} has invalid format."

    MIN_LENGTH = "{field} is too short (minimum {min} characters)."
    MAX_LENGTH = "{field} is too long (maximum {max} characters)."
    INVALID_PATTERN = "{field} contains invalid characters or format."

    # Username
    USERNAME_INVALID_CHARS = "Username must start with a letter or '_' and contain only a-z, 0-9, '_', or '.'"
    USERNAME_CONSECUTIVE_DOTS = "Username cannot contain consecutive dots."
    USERNAME_TRAILING_DOT = "Username cannot end with a dot."
    USERNAME_NO_ALPHA = "Username must contain at least one alphabet character."

    # Password
    PASSWORD_NO_DIGIT = "Password must contain at least one number."
    PASSWORD_NO_LOWER = "Password must contain at least one lowercase letter."
    PASSWORD_NO_UPPER = "Password must contain at least one uppercase letter."
    PASSWORD_NO_SYMBOL = (
        "Password must contain at least one special character (e.g. !@#$)."
    )

    # Names
    NAME_INVALID_CHARS = "{field} can only contain letters, spaces, and apostrophes."

    FILE_EMPTY = "Uploaded file is empty."
    FILE_INVALID_TYPE = "Invalid file type ({type}). Allowed: {allowed_types}"
    FILE_TOO_LARGE = "File size exceeds the maximum allowed ({max_mb} MB)."
