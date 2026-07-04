from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_timestamp() -> int:
    return int(utc_now().timestamp())


def utc_now_format(fmt: str) -> str:
    return utc_now().strftime(fmt)
