from enum import Enum


class UserStatus(str, Enum):
    PENDING = "pending"  # registered but not verified
    ACTIVE = "active"  # verified and used
    EXPIRED = "expired"  # never verified, grace period passed
    DELETED = "deleted"  # user intentionally deleted account

    def __repr__(self) -> str:
        return self.value
