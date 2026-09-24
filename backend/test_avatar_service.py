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
