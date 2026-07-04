import time
from dataclasses import dataclass

from app.users.models import User


@dataclass(frozen=True)
class JwtContext:
    sub: int
    jti: str
    exp: int

    @classmethod
    def from_payload(cls, payload: dict) -> "JwtContext":
        try:
            return cls(
                sub=int(payload["sub"]),
                jti=str(payload["jti"]),
                exp=int(payload["exp"]),
            )
        except (KeyError, ValueError, TypeError):
            raise ValueError("Invalid JWT payload structure")

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.exp - int(time.time()))

    @property
    def is_expired(self) -> bool:
        return self.remaining_seconds == 0


@dataclass
class AuthContext:
    user: User
    jwt: JwtContext
