import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.media.schemas import MediaPublic

from .validator_types import (
    FirstNameOptional,
    FirstNameRequired,
    LastNameOptionalAllowNull,
    PasswordRequired,
    UsernameOptional,
    UsernameRequired,
)


class UserBase(BaseModel):
    """Shared properties for a User."""

    username: UsernameRequired
    first_name: FirstNameRequired
    last_name: LastNameOptionalAllowNull = None
    email: EmailStr


class UserCreate(UserBase):
    """Properties required to create a new user."""

    password: PasswordRequired


class UserUpdate(BaseModel):
    """Properties to update an existing user. All are optional."""

    username: UsernameOptional = None
    first_name: FirstNameOptional = None
    last_name: LastNameOptionalAllowNull = None


class UserPublic(UserBase):
    """Properties to return to the client."""

    id: int
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None

    # --- MAGIC HAPPENS HERE ---
    # 1. The name 'profile_image' matches User.profile_image relationship.
    # 2. The type 'MediaPublic' tells Pydantic how to format it.
    # 3. Pydantic automatically runs the logic inside MediaPublic (including get_url).
    profile_image: Optional[MediaPublic] = None

    # OPTIONAL: If you really want the JSON key to be 'profile_picture'
    # but the DB relationship is 'profile_image', use serialization_alias:
    # profile_image: Optional[MediaPublic] = Field(None, serialization_alias="profile_picture")

    model_config = ConfigDict(from_attributes=True)
