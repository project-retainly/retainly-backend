import sqlalchemy as sa
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models_common import TimestampMixin
from app.core.database import Base

from .utils import UserStatus


class User(Base, TimestampMixin):
    __tablename__ = "users"

    __table_args__ = (
        Index(
            "uq_users_email_active_pending",
            "email",
            unique=True,
            postgresql_where=sa.text("status IN ('pending','active')"),
        ),
        Index(
            "uq_users_username_active_pending",
            "username",
            unique=True,
            postgresql_where=sa.text("status IN ('pending','active')"),
        ),
    )

    # SQLAlchemy handles 'increment' (autoincrement) automatically
    # for integer primary keys.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    username: Mapped[str] = mapped_column(String(150), index=True, nullable=False)

    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    first_name: Mapped[str] = mapped_column(String(70), nullable=False)

    last_name: Mapped[str | None] = mapped_column(String(70))

    password: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[UserStatus] = mapped_column(
        SAEnum(
            UserStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=UserStatus.PENDING,
        nullable=False,
    )

    profile_image_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "media.id",
            name="fk_user_profile_image",
            use_alter=True,  # Defer FK creation to avoid circular dependency with Media
        ),
        nullable=True,
    )

    profile_image: Mapped["Media"] = relationship(  # type: ignore # noqa: F821
        "Media", foreign_keys=[profile_image_id], uselist=False, lazy="selectin"
    )

    # This matches the "owner" relationship in the Post model
    posts: Mapped[list["Post"]] = relationship(  # type: ignore  # noqa: F821
        "Post",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(  # type: ignore  # noqa: F821
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",  # When user deleted, delete all their tokens
        # lazy="selectin",  # or "dynamic" for large numbers of tokens
    )

    media_uploads: Mapped[list["Media"]] = relationship(  # type: ignore  # noqa: F821
        "Media",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic",
        foreign_keys="[Media.user_id]",  # Explicitly target the user_id column
    )

    def __repr__(self):  # pragma: no cover
        return f"<User(id={self.id!r}, username={self.username!r}, email={self.email!r}, status={self.status!r})>"
