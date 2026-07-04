from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models_common import TimestampMixin
from app.core.database import Base

from .utils import MediaStatus


class Media(TimestampMixin, Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(primary_key=True)

    # File Metadata
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status: Store as String in DB, behave as Enum in Python
    # native_enum=False creates a VARCHAR column with a CHECK constraint (Best of both worlds)
    status: Mapped[MediaStatus] = mapped_column(
        SAEnum(
            MediaStatus,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=MediaStatus.ACTIVE,
        nullable=False,
    )

    # Ownership
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_media_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    usages: Mapped[list["MediaUsage"]] = relationship(
        "MediaUsage",
        back_populates="media",
        cascade="all, delete-orphan",
    )

    user: Mapped["User"] = relationship(  # type: ignore # noqa: F821
        "User", back_populates="media_uploads", foreign_keys=[user_id]
    )

    def __repr__(self):
        return (
            f"<Media id={self.id} "
            f"filename='{self.filename}' "
            f"type='{self.media_type}' "
            f"status='{self.status.value}'>"
        )


class MediaUsage(TimestampMixin, Base):
    __tablename__ = "media_usage"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Generic association (polymorphic)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)

    # Usage context
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    block_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Active flag (for updates/diffing)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # FK → media
    media_id: Mapped[int] = mapped_column(
        ForeignKey("media.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationship
    media: Mapped["Media"] = relationship(
        "Media",
        back_populates="usages",
    )

    __table_args__ = (
        # Fast lookup: all media for a post
        Index("idx_entity_lookup", "entity_type", "entity_id"),
        # Prevent duplicate mappings for same block
        Index(
            "uq_media_usage_block",
            "media_id",
            "entity_type",
            "entity_id",
            "block_id",
            unique=True,
        ),
    )

    def __repr__(self):
        return (
            f"<MediaUsage media_id={self.media_id} "
            f"entity={self.entity_type}:{self.entity_id} "
            f"field={self.field_name}>"
        )
