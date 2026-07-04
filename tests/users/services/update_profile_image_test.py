from sqlalchemy.ext.asyncio import AsyncSession

from app.core.validations.file_validator import AnalyzedFile
from app.media.services import MediaService
from app.media.utils import StaticDirs
from app.users.services import UserService
from tests.file_factory import FileFactory, FilePresets
from tests.media.factories import MediaFactory
from tests.users.factories import UserFactory


class TestUpdateProfileImageService:
    async def test_success_upload_new_profile_image(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await UserFactory.create()

        mock_media = await MediaFactory.create(
            user_id=user.id,
            filename="new_avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/new_avatar.jpg",
        )

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)
        analyzed_file = AnalyzedFile(file=file)

        async def mock_upload(self, *args, **kwargs):
            return mock_media

        monkeypatch.setattr(MediaService, "upload_file_and_create_media", mock_upload)

        service = UserService(db_session)
        result = await service.update_profile_image(user, analyzed_file)

        assert result.profile_image_id == mock_media.id
        assert result.profile_image == mock_media

    async def test_success_replace_existing_profile_image(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await UserFactory.create()

        old_media = await MediaFactory.create(
            user_id=user.id,
            filename="old_avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/old_avatar.jpg",
        )
        user.profile_image_id = old_media.id
        await db_session.commit()
        await db_session.refresh(user)

        new_media = await MediaFactory.create(
            user_id=user.id,
            filename="new_avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/new_avatar.jpg",
        )

        file = FileFactory.create(file_type=FilePresets.PNG, size_mb=2)
        analyzed_file = AnalyzedFile(file=file)

        delete_called = False

        async def mock_delete(self, media):
            nonlocal delete_called
            delete_called = True
            assert media.id == old_media.id

        async def mock_upload(self, *args, **kwargs):
            return new_media

        monkeypatch.setattr(MediaService, "delete_media", mock_delete)
        monkeypatch.setattr(MediaService, "upload_file_and_create_media", mock_upload)

        service = UserService(db_session)
        result = await service.update_profile_image(user, analyzed_file)

        assert delete_called is True
        assert result.profile_image_id == new_media.id
        assert result.profile_image == new_media

    async def test_success_no_existing_profile_image(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await UserFactory.create()
        user.profile_image_id = None
        await db_session.commit()

        new_media = await MediaFactory.create(
            user_id=user.id,
            filename="first_avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/first_avatar.jpg",
        )

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)
        analyzed_file = AnalyzedFile(file=file)

        delete_called = False

        async def mock_delete(media):
            nonlocal delete_called
            delete_called = True

        async def mock_upload(*args, **kwargs):
            return new_media

        monkeypatch.setattr(MediaService, "delete_media", mock_delete)
        monkeypatch.setattr(MediaService, "upload_file_and_create_media", mock_upload)

        service = UserService(db_session)
        result = await service.update_profile_image(user, analyzed_file)

        assert delete_called is False
        assert result.profile_image_id == new_media.id

    async def test_success_commits_transaction(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await UserFactory.create()

        new_media = await MediaFactory.create(
            user_id=user.id,
            filename="avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/avatar.jpg",
        )

        analyzed_file = AnalyzedFile(
            file=FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)
        )

        async def mock_upload(*args, **kwargs):
            return new_media

        monkeypatch.setattr(MediaService, "upload_file_and_create_media", mock_upload)

        commit_called = False
        original_commit = db_session.commit

        async def mock_commit():
            nonlocal commit_called
            commit_called = True
            await original_commit()

        monkeypatch.setattr(db_session, "commit", mock_commit)

        service = UserService(db_session)
        await service.update_profile_image(user, analyzed_file)

        assert commit_called is True

    async def test_success_refreshes_user_after_commit(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await UserFactory.create()

        new_media = await MediaFactory.create(
            user_id=user.id,
            filename="avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/avatar.jpg",
        )

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)
        analyzed_file = AnalyzedFile(file=file)

        async def mock_upload(*args, **kwargs):
            return new_media

        monkeypatch.setattr(MediaService, "upload_file_and_create_media", mock_upload)

        refresh_called = False
        original_refresh = db_session.refresh

        async def mock_refresh(obj):
            nonlocal refresh_called
            refresh_called = True
            await original_refresh(obj)

        monkeypatch.setattr(db_session, "refresh", mock_refresh)

        service = UserService(db_session)
        await service.update_profile_image(user, analyzed_file)

        assert refresh_called is True

    async def test_success_uploads_to_correct_directory(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await UserFactory.create()

        new_media = await MediaFactory.create(
            user_id=user.id,
            filename="avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/avatar.jpg",
        )

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)
        analyzed_file = AnalyzedFile(file=file)

        captured_directory = None

        async def mock_upload(self, file, user_id, directory):
            nonlocal captured_directory
            captured_directory = directory
            return new_media

        monkeypatch.setattr(MediaService, "upload_file_and_create_media", mock_upload)

        service = UserService(db_session)
        await service.update_profile_image(user, analyzed_file)

        assert captured_directory == StaticDirs.Uploads.AVATARS

    async def test_success_links_media_to_user(
        self, db_session: AsyncSession, monkeypatch
    ):
        user = await UserFactory.create()

        new_media = await MediaFactory.create(
            user_id=user.id,
            filename="avatar.jpg",
            file_path=f"{StaticDirs.Uploads.AVATARS}/avatar.jpg",
        )

        file = FileFactory.create(file_type=FilePresets.JPEG, size_mb=1)
        analyzed_file = AnalyzedFile(file=file)

        async def mock_upload(*args, **kwargs):
            return new_media

        monkeypatch.setattr(MediaService, "upload_file_and_create_media", mock_upload)

        service = UserService(db_session)
        result = await service.update_profile_image(user, analyzed_file)

        assert result.profile_image == new_media
        assert user.profile_image == new_media
        assert user.profile_image_id == new_media.id
