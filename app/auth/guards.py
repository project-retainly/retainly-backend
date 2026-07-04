from fastapi import HTTPException, status

from app.core.settings import settings


def registration_guard():
    """
    Single-tenant guard. Blocks all public registration.
    When going multi-tenant: replace body with invite-token
    or admin-approval logic — routes stay untouched.
    """
    if not settings.REGISTRATION_OPEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is currently closed.",
        )
