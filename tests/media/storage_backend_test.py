import os

import aiofiles
import pytest

from app.core.storage import LocalStorage
from tests.file_factory import FileFactory, FilePresets


class TestLocalStorage:
    @pytest.fixture(autouse=True)
    def setup_storage(self, tmp_path):
        """
        Injects a temporary directory into the LocalStorage instance
        to ensure we don't write to the real static folder.
        """
        self.storage = LocalStorage()
        self.storage.upload_dir = tmp_path
        self.tmp_dir = tmp_path

    @pytest.mark.asyncio
    async def test_upload_saves_file_correctly(self):
        # Arrange
        file = FileFactory.create(file_type=FilePresets.TEXT, filename="hello.txt")
        # Manually write content to the mock file for verification
        content = b"Hello World"
        FileFactory.set_content(file, content)

        destination = "uploads/2024/hello.txt"

        # Act
        saved_path = await self.storage.upload(file, destination)

        # Assert
        assert saved_path == destination
        full_path = self.tmp_dir / destination
        assert full_path.exists()

        # Verify content integrity
        async with aiofiles.open(full_path, "rb") as f:
            saved_content = await f.read()
        assert saved_content == content

    @pytest.mark.asyncio
    async def test_upload_creates_nested_directories(self):
        # Arrange
        file = FileFactory.create()
        destination = "deeply/nested/folder/structure/image.jpg"

        # Act
        await self.storage.upload(file, destination)

        # Assert
        full_path = self.tmp_dir / destination
        assert full_path.exists()
        assert full_path.parent.is_dir()

    @pytest.mark.asyncio
    async def test_delete_removes_existing_file(self):
        # Arrange
        destination = "uploads/todelete.jpg"
        # Create a dummy file first
        full_path = self.tmp_dir / destination
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write("dummy")

        assert full_path.exists()

        # Act
        await self.storage.delete(destination)

        # Assert
        assert not full_path.exists()

    @pytest.mark.asyncio
    async def test_delete_handles_non_existent_file_silently(self):
        # Arrange
        path = "non_existent/file.jpg"

        # Act & Assert
        # Should not raise any exception
        await self.storage.delete(path)
