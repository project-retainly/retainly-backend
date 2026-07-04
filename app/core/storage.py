import os
from abc import ABC, abstractmethod

import aiofiles
from fastapi import UploadFile

from app.core.settings import settings


class StorageBackend(ABC):
    @abstractmethod
    def get_url(self, path: str):
        pass

    @abstractmethod
    async def upload(self, file: UploadFile, destination: str) -> str:
        """Uploads file and returns the relative path/key"""
        pass

    @abstractmethod
    async def delete(self, path: str):
        pass


class LocalStorage(StorageBackend):
    def __init__(self):
        self.upload_dir = settings.MEDIA_DIR

    def get_url(self, path: str) -> str:
        return f"{settings.BACKEND_HOST_URL}/media/{path}"

    async def upload(self, file: UploadFile, destination: str) -> str:
        full_path = os.path.join(self.upload_dir, destination)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        async with aiofiles.open(full_path, "wb") as out_file:
            content = await file.read()  # async read
            await out_file.write(content)

        return destination

    async def delete(self, path: str):
        full_path = os.path.join(self.upload_dir, path)
        if os.path.exists(full_path):
            os.remove(full_path)


# Factory Function
def get_storage_backend() -> StorageBackend:
    if settings.USE_CLOUD_STORAGE:
        # return CloudStorage() # Implement later!
        raise NotImplementedError("Cloud not ready yet")
    return LocalStorage()
