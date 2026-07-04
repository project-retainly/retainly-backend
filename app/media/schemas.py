from typing import Optional

from pydantic import BaseModel, Field, computed_field

from app.core.storage import get_storage_backend


class MediaPublic(BaseModel):
    id: int
    filename: str

    file_path: str = Field(exclude=True)  # Exclude from output, used internally

    @computed_field
    def url(self) -> Optional[str]:
        if self.file_path:
            backend = get_storage_backend()
            return backend.get_url(self.file_path)
        return None
