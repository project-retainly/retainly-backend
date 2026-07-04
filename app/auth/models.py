from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # Composite index for common query pattern: active tokens for a user
    __table_args__ = (
        Index("ix_refresh_tokens_expires_at", "expires_at"),
        Index(
            "ix_refresh_tokens_user_active",
            "user_id",
            "revoked_at",
            "expires_at",
        ),
        Index("ix_refresh_tokens_replaced_by", "replaced_by_token_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", name="fk_refresh_token_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 2. The Token (IMPORTANT: Store hash, not plaintext!)
    # Security Best Practice: Store bcrypt/SHA256 hash of the token
    # Return the actual token only once when created
    token_hash = Column(String, unique=True, index=True, nullable=False)

    # 3. Lifecycle Management
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Track WHY it was revoked (useful for security audits)
    revocation_reason = Column(
        String, nullable=True
    )  # "logout", "suspicious_activity", "token_rotation", "admin_revoke"

    # 4. Security Metadata
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    # 5. Token Rotation Support (Reuse Detection)
    replaced_by_token_hash = Column(String, nullable=True, index=True)

    user = relationship("User", back_populates="refresh_tokens")

    @property
    def is_expired(self) -> bool:
        """Check if token has passed expiration time"""
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def is_revoked(self) -> bool:
        """Check if token was explicitly revoked"""
        return self.revoked_at is not None

    @property
    def is_active(self) -> bool:
        """Check if token is valid for use"""
        return not self.is_revoked and not self.is_expired

    @property
    def is_replaced(self) -> bool:
        """Check if this token was replaced by another (token rotation)"""
        return self.replaced_by_token_hash is not None

    @property
    def age_in_seconds(self) -> float:
        """Get token age in seconds"""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    def revoke(
        self,
        reason: str,
        request: Request,
        token_replaced_by: str | None = None,
    ) -> None:
        """Revoke the token with a given reason."""
        self.revoked_at = datetime.now(timezone.utc)
        self.revocation_reason = reason
        self.replaced_by_token_hash = token_replaced_by
        self.user_agent = request.headers.get("User-Agent")
        self.ip_address = request.client.host if request.client else None
