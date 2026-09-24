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
