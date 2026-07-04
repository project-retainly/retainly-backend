import json
import re
from typing import Any, Callable

import regex

from .messages import Msg

# ---------- REJECT NULL ----------


def reject_null(field_name: str):
    def validator(v, handler):
        if v is None:
            raise ValueError(json.dumps([Msg.FIELD_NULL.format(field=field_name)]))
        return handler(v)

    return validator


# ---------- NOT EMPTY ----------


def not_empty(field_name: str) -> Callable:
    def validator(v: Any):
        # String: strip and check
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError(Msg.FIELD_EMPTY.format(field=field_name))
            return v

        # Collections: list, dict, set, tuple
        if isinstance(v, (list, dict, set, tuple)):
            if len(v) == 0:
                raise ValueError(Msg.FIELD_EMPTY.format(field=field_name))
            return v

        # Other types: reject falsy values explicitly if desired
        # (optional — depends on your design philosophy)
        return v

    return validator


# ---------- LENGTH ----------


def length(field_name: str, min_len: int, max_len: int) -> Callable:
    def validator(v: str):
        if v is None:
            return v
        length = len(v)
        if length < min_len:
            raise ValueError(
                json.dumps([Msg.MIN_LENGTH.format(field=field_name, min=min_len)])
            )
        if length > max_len:
            raise ValueError(
                json.dumps([Msg.MAX_LENGTH.format(field=field_name, max=max_len)])
            )
        return v

    return validator


# ---------- HUMAN NAME ----------


def human_name(field_name: str) -> Callable:
    NAME_REGEX = regex.compile(r"^[\p{L}\p{M}]+(?:[ '][\p{L}\p{M}]+)*$")

    def validator(v: str):
        if not NAME_REGEX.fullmatch(v):
            raise ValueError(
                json.dumps([Msg.NAME_INVALID_CHARS.format(field=field_name)])
            )
        return v

    return validator


# ---------- USERNAME ----------


def username_rules() -> Callable:
    def validator(v: str):
        v = v.lower()

        errors = []

        if not re.search(r"[a-z]", v):
            errors.append(Msg.USERNAME_NO_ALPHA)

        if not re.match(r"^[a-z_][a-z0-9_.]*$", v):
            errors.append(Msg.USERNAME_INVALID_CHARS)

        if ".." in v:
            errors.append(Msg.USERNAME_CONSECUTIVE_DOTS)

        if v.endswith("."):
            errors.append(Msg.USERNAME_TRAILING_DOT)

        if errors:
            raise ValueError(json.dumps(errors))
        return v

    return validator


# ---------- PASSWORD ----------


def password_rules() -> Callable:
    def validator(v: str):
        errors = []

        if not re.search(r"\d", v):
            errors.append(Msg.PASSWORD_NO_DIGIT)

        if not re.search(r"[a-z]", v):
            errors.append(Msg.PASSWORD_NO_LOWER)

        if not re.search(r"[A-Z]", v):
            errors.append(Msg.PASSWORD_NO_UPPER)

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>~]", v):
            errors.append(Msg.PASSWORD_NO_SYMBOL)

        if errors:
            raise ValueError(json.dumps(errors))
        return v

    return validator
