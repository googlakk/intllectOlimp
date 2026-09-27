import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from models import Profile, Student, Teacher
from services.accounts import temporary_password
from services.auth import AuthPrincipal, AuthServiceError, principal_for_auth_user, serialize_principal, user_model_for_role
from services.supabase_auth import SupabaseAuthError, admin_create_auth_user, auth_email, normalize_login


class AuthServiceTests(unittest.TestCase):
    def test_principal_is_serialized_without_access_token(self):
        principal = AuthPrincipal(
            profile_id=11,
            auth_user_id=UUID("00000000-0000-0000-0000-000000000001"),
            organization_id=2,
            role="student",
            login_name="alina.7a",
            display_name="Алина",
            must_change_password=True,
            teacher_id=None,
            student_id=5,
            grade=7,
            access_token="secret-token",
        )
        self.assertEqual(
            serialize_principal(principal),
            {
                "id": 5,
                "profile_id": 11,
                "name": "Алина",
                "login_name": "alina.7a",
                "role": "student",
                "grade": 7,
                "must_change_password": True,
            },
        )

    def test_role_selects_legacy_learning_identity(self):
        self.assertIs(user_model_for_role("student"), Student)
        self.assertIs(user_model_for_role("teacher"), Teacher)
        with self.assertRaises(AuthServiceError):
            user_model_for_role("admin")

    def test_login_is_normalized_and_mapped_to_private_auth_email(self):
        self.assertEqual(normalize_login("  Student.7A "), "student.7a")
        self.assertEqual(auth_email("Student.7A"), "student.7a@users.intellect.local")
        with self.assertRaises(SupabaseAuthError):
            normalize_login("Алина")

    def test_temporary_password_is_strong_and_not_deterministic(self):
        first = temporary_password()
        second = temporary_password()
        self.assertNotEqual(first, second)
        self.assertGreaterEqual(len(first), 12)
        self.assertTrue(any(char.islower() for char in first))
        self.assertTrue(any(char.isupper() for char in first))
        self.assertTrue(any(char.isdigit() for char in first))


class PrincipalLookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_provisioning_marks_auth_user_as_backend_created(self):
        with patch("services.supabase_auth._request", new=AsyncMock(return_value={"id": "user"})) as request:
            await admin_create_auth_user(
                login="student.7a",
                password="Temporary123!",
                display_name="Student",
                role="student",
            )

        payload = request.await_args.kwargs["payload"]
        self.assertEqual(payload["app_metadata"], {
            "provisioned_by": "intellect-backend",
            "platform_role": "student",
        })

    async def test_blocked_profile_returns_machine_readable_terminal_code(self):
        blocked = Profile(
            id=11,
            auth_user_id=UUID("00000000-0000-0000-0000-000000000001"),
            organization_id=2,
            role="student",
            login_name="student.7a",
            display_name="Student",
            status="blocked",
            must_change_password=False,
            student_id=5,
        )
        result = MagicMock()
        result.one_or_none.return_value = (blocked, 7)
        db = MagicMock()
        db.execute = AsyncMock(return_value=result)

        with self.assertRaises(AuthServiceError) as error:
            await principal_for_auth_user(str(blocked.auth_user_id), "token", db)

        self.assertEqual(error.exception.status_code, 403)
        self.assertEqual(error.exception.code, "account_blocked")


if __name__ == "__main__":
    unittest.main()


class AuthCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from services import auth, supabase_auth
        supabase_auth._verified_tokens.clear()
        auth._principals.clear()

    @staticmethod
    def token(expires_in: float) -> str:
        import base64
        import json
        import time
        claims = base64.urlsafe_b64encode(json.dumps({"exp": time.time() + expires_in}).encode()).decode().rstrip("=")
        return f"header.{claims}.signature"

    async def test_verified_token_is_reused_until_logout(self):
        from services.supabase_auth import forget_auth_token, get_auth_user
        token = self.token(3600)
        with patch("services.supabase_auth._request", new=AsyncMock(return_value={"id": "u1"})) as request:
            self.assertEqual(await get_auth_user(token), {"id": "u1"})
            self.assertEqual(await get_auth_user(token), {"id": "u1"})
            self.assertEqual(request.await_count, 1)
            forget_auth_token(token)
            await get_auth_user(token)
            self.assertEqual(request.await_count, 2)

    async def test_token_close_to_expiry_is_not_cached(self):
        from services.supabase_auth import get_auth_user
        token = self.token(3)
        with patch("services.supabase_auth._request", new=AsyncMock(return_value={"id": "u1"})) as request:
            await get_auth_user(token)
            await get_auth_user(token)
            self.assertEqual(request.await_count, 2)

    async def test_principal_is_cached_until_forgotten(self):
        from services.auth import forget_principal
        profile = Profile(id=12, auth_user_id=UUID("00000000-0000-0000-0000-000000000002"), organization_id=2, role="student",
                          login_name="s", display_name="S", status="active", must_change_password=True, student_id=5)
        result = MagicMock()
        result.one_or_none.return_value = (profile, 7)
        db = MagicMock()
        db.execute = AsyncMock(return_value=result)
        first = await principal_for_auth_user(str(profile.auth_user_id), "t1", db)
        second = await principal_for_auth_user(str(profile.auth_user_id), "t2", db)
        self.assertEqual(db.execute.await_count, 1)
        self.assertEqual((first.access_token, second.access_token), ("t1", "t2"))
        forget_principal(profile.auth_user_id)
        await principal_for_auth_user(str(profile.auth_user_id), "t3", db)
        self.assertEqual(db.execute.await_count, 2)
