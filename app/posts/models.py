from datetime import datetime
from typing import Any, Optional

from nanoid import generate
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models_common import TimestampMixin
from app.core.database import Base

from .utils import PostStatus


def short_id(size=10) -> str:
    # Generate a short, URL-friendly ID using nanoid
    return generate(size=size)


class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(
        String(10), primary_key=True, index=True, default=lambda: short_id()
    )

    # 1. SEO & URLs
    slug: Mapped[str] = mapped_column(String, unique=True)
    title: Mapped[str] = mapped_column(String, index=True)

    # 2. Editor.js Data
    # We use JSONB because it's faster to query/index
    # in Postgres than standard JSON text.
    # It will store: { "time": 1678..., "blocks": [...] }
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)

    # 3. Meta / UI fields
    # A short text version for the blog home page
    # (so you don't load the full JSON)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[PostStatus] = mapped_column(
        SAEnum(
            PostStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=PostStatus.DRAFT,
        nullable=False,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    featured_image_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "media.id",
            name="fk_post_featured_image",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_post_user", ondelete="CASCADE")
    )

    featured_image: Mapped["Media"] = relationship(  # type: ignore # noqa: F821
        "Media",
        foreign_keys=[featured_image_id],
        uselist=False,
        lazy="selectin",
    )

    owner: Mapped["User"] = relationship("User", back_populates="posts")  # type: ignore  # noqa: F821

    def __repr__(self):  # pragma: no cover
        return f"<Post(id={self.id!r}, title={self.title!r})>"
