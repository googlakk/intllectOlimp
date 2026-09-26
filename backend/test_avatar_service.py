import unittest
from types import SimpleNamespace

from llm.heygen import HeyGenAvatarLook
from models import AvatarProfile, LessonVersion, Teacher
from services.avatar import (
    AvatarServiceError,
    create_custom_photo_profile,
    refresh_custom_photo_profile,
    submit_avatar_job,
    validate_custom_avatar_image,
)


class FakeProvider:
    async def create_photo_avatar(self, **_kwargs):
        return HeyGenAvatarLook(
            id="look-1",
            group_id="group-1",
            status="processing",
            preview_image_url="https://cdn/preview.png",
        )

    async def get_avatar_look(self, _look_id):
        return HeyGenAvatarLook(
            id="look-1",
            group_id="group-1",
            status="completed",
            preview_image_url="https://cdn/ready.png",
            default_voice_id="voice-default",
        )


class FakeSession:
    def __init__(self):
        self.teacher = Teacher(id=7, name="Учитель")
        self.profile = None

    async def get(self, model, row_id):
        if model is Teacher and row_id == self.teacher.id:
            return self.teacher
        if model is LessonVersion and row_id == 5:
            return SimpleNamespace(id=5)
        if model is AvatarProfile and self.profile is not None and row_id == self.profile.id:
            return self.profile
        return None

    def add(self, row):
        self.profile = row
        row.id = 11
        row.is_active = True

    async def commit(self):
        return None

    async def refresh(self, _row):
        return None


class AvatarUploadTests(unittest.IsolatedAsyncioTestCase):
    def test_validates_image_signature_and_size(self):
        self.assertEqual(validate_custom_avatar_image(b"\xff\xd8\xffphoto", "image/jpeg"), "image/jpeg")
        with self.assertRaises(AvatarServiceError):
            validate_custom_avatar_image(b"not-an-image", "image/png")

    async def test_creates_and_refreshes_custom_photo_profile(self):
        db = FakeSession()
        profile = await create_custom_photo_profile(
            name="Мой аватар",
            teacher_id=7,
            image=b"\x89PNG\r\n\x1a\nphoto",
            content_type="image/png",
            filename="portrait.png",
            rights_confirmed=True,
            voice_id=None,
            db=db,
            provider=FakeProvider(),
        )

        self.assertEqual(profile.provider_avatar_id, "look-1")
        self.assertEqual(profile.consent_metadata["status"], "processing")
        self.assertTrue(profile.consent_metadata["rights_confirmed"])

        refreshed = await refresh_custom_photo_profile(profile.id, db, provider=FakeProvider())

        self.assertEqual(refreshed.consent_metadata["status"], "completed")
        self.assertEqual(refreshed.preview_image_url, "https://cdn/ready.png")
        self.assertEqual(refreshed.provider_voice_id, "voice-default")

    async def test_requires_rights_confirmation(self):
        with self.assertRaises(AvatarServiceError) as rejected:
            await create_custom_photo_profile(
                name="Чужой аватар",
                teacher_id=7,
                image=b"\xff\xd8\xffphoto",
                content_type="image/jpeg",
                filename="photo.jpg",
                rights_confirmed=False,
                voice_id=None,
                db=FakeSession(),
                provider=FakeProvider(),
            )

        self.assertEqual(rejected.exception.detail, "Подтвердите право использовать изображение")

    async def test_rejects_generation_while_photo_avatar_is_processing(self):
        db = FakeSession()
        db.profile = AvatarProfile(
            id=11,
            name="Мой аватар",
            provider_avatar_id="look-1",
            provider_voice_id="voice-1",
            is_active=True,
            consent_metadata={"source": "teacher_photo_upload", "status": "processing"},
        )

        with self.assertRaises(AvatarServiceError) as rejected:
            await submit_avatar_job(SimpleNamespace(
                lesson_version_id=5,
                profile_id=11,
                scene_id="scene-1",
                script="Объяснение",
                locale="ru-RU",
            ), db)

        self.assertEqual(rejected.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()


class AvatarVideoUrlTests(unittest.IsolatedAsyncioTestCase):
    async def test_private_videos_signed_in_one_call_and_cached(self):
        from types import SimpleNamespace
        from services import avatar as service

        service._signed_url_cache.clear()
        calls = []

        class Storage:
            async def create_signed_urls(self, *, bucket, paths, expires_in):
                calls.append((bucket, list(paths), expires_in))
                return {path: f"https://cdn/{path}?token=1" for path in paths}

        private = [SimpleNamespace(id=index, storage_bucket=service.AVATAR_VIDEO_BUCKET, storage_path=f"lessons/1/{index}.mp4",
                                   source_url=f"storage:{service.AVATAR_VIDEO_BUCKET}/lessons/1/{index}.mp4") for index in (1, 2)]
        legacy = SimpleNamespace(id=3, storage_bucket="lesson-assets", storage_path="x.mp4", source_url="https://public/x.mp4")

        urls = await service.avatar_video_urls([*private, legacy], storage=Storage())
        again = await service.avatar_video_urls(private, storage=Storage())

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], ["lessons/1/1.mp4", "lessons/1/2.mp4"])
        self.assertEqual(urls[1], "https://cdn/lessons/1/1.mp4?token=1")
        self.assertEqual(urls[3], "https://public/x.mp4")
        self.assertEqual(again[2], urls[2])


class MissingBucketTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_private_bucket_fails_job_with_clear_message(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        from llm import LLMError
        from llm.heygen import HeyGenVideoJob
        from services import avatar as service

        job = SimpleNamespace(id=5, provider="heygen", external_job_id="v1", status="processing", request_payload={"api_version": "v3"},
                              lesson_version_id=9, scene_id="scene-1", result_payload=None, error=None, completed_at=None, updated_at=None)

        class Session:
            async def get(self, _model, _id):
                return job

            async def commit(self):
                pass

            async def refresh(self, _row):
                pass

        class Provider:
            async def get_video(self, _video_id, *, api_version):
                return HeyGenVideoJob(id="v1", status="completed", video_url="https://heygen/v1.mp4", raw={})

        class Storage:
            def configured(self):
                return True

            async def copy_from_url(self, **_kwargs):
                raise LLMError("Хранилище отклонило файл (400): {\"error\":\"Bucket not found\"}", provider="supabase-storage")

        with patch.object(service, "_avatar_draft_version", AsyncMock(return_value=9)):
            result = await service.refresh_avatar_job(5, Session(), provider=Provider(), storage=Storage())  # type: ignore[arg-type]

        self.assertEqual(result.status, "failed")
        self.assertIn("avatar-videos", result.error["message"])
