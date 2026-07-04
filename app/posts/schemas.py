from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict

from app.media.schemas import MediaPublic

from .utils import PostStatus
from .validator_types import (
    ContentOptionalAllowNull,
    StatusOptional,
    StatusRequired,
    SummaryOptionalAllowNull,
    TitleOptional,
    TitleRequired,
)


# 1. Base Schema (Shared light properties)
# We keep this lightweight so the List View doesn't load heavy JSON content.
class PostBase(BaseModel):
    title: TitleRequired
    summary: SummaryOptionalAllowNull = None

    # Defaults to DRAFT, validates against your Enum
    status: StatusRequired = PostStatus.DRAFT


# 2. CREATE Schema (Receive from user)
class PostCreate(PostBase):
    # We use Dict[str, Any] to match Editor.js JSON structure
    content: ContentOptionalAllowNull


# 3. UPDATE Schema (Partial updates)
class PostUpdate(BaseModel):
    title: TitleOptional = None

    # User might update the content blocks
    content: ContentOptionalAllowNull = None
    summary: SummaryOptionalAllowNull = None
    status: StatusOptional = None


# 4. RESPONSE Schema (Full Detail View)
# Used for GET /posts/{slug}
class PostResponse(PostBase):
    id: str
    slug: str
    user_id: int

    # The full JSON content is only included here
    content: Dict[str, Any]
    status: PostStatus

    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    featured_image: Optional[MediaPublic] = None

    model_config = ConfigDict(from_attributes=True)


# 5. LIST Response Schema (Lightweight View)
# Used for GET /posts/
class PostListResponse(PostBase):
    id: str
    slug: str
    user_id: int

    # NO 'content' field here.
    # This makes the homepage load 10x faster.
    featured_image: Optional[MediaPublic] = None

    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
