import unittest
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.security import HTTPAuthorizationCredentials

from auth_dependencies import get_current_user, require_roles
from services.supabase_auth import SupabaseAuthError
from services.auth import AuthPrincipal, AuthServiceError


def principal(*, role: str = "teacher", must_change_password: bool = False) -> AuthPrincipal:
    return AuthPrincipal(
        profile_id=1,
        auth_user_id=UUID("00000000-0000-0000-0000-000000000001"),
        organization_id=1,
        role=role,
        login_name="user.one",
        display_name="User One",
        must_change_password=must_change_password,
        teacher_id=1 if role == "teacher" else None,
        student_id=1 if role == "student" else None,
        grade=7 if role == "student" else None,
        access_token="token",
    )


class AuthDependenciesTests(unittest.IsolatedAsyncioTestCase):
    async def test_role_dependency_accepts_allowed_role(self):
        user = principal(role="teacher")
        self.assertIs(await require_roles("admin", "teacher")(user), user)

    async def test_role_dependency_rejects_wrong_role(self):
        with self.assertRaises(AuthServiceError) as error:
            await require_roles("admin")(principal(role="teacher"))
        self.assertEqual(error.exception.status_code, 403)

    async def test_temporary_password_blocks_normal_routes(self):
        with self.assertRaises(AuthServiceError):
            await require_roles("student")(principal(role="student", must_change_password=True))
        user = principal(role="student", must_change_password=True)
        self.assertIs(await require_roles("student", password_change_allowed=True)(user), user)


if __name__ == "__main__":
    unittest.main()


class CurrentUserTokenTests(unittest.IsolatedAsyncioTestCase):
    async def _resolve(self, error: SupabaseAuthError):
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="expired-token")
        with patch("auth_dependencies.get_auth_user", AsyncMock(side_effect=error)):
            return await get_current_user(credentials, db=None)

    async def test_expired_token_is_reported_as_401_so_client_refreshes(self):
        # Supabase отвечает 403 «invalid JWT» на истёкший токен.
        with self.assertRaises(AuthServiceError) as error:
            await self._resolve(SupabaseAuthError(status_code=403, detail="invalid JWT: token is expired"))
        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(error.exception.code, "session_expired")

    async def test_supabase_outage_is_not_hidden_as_session_problem(self):
        with self.assertRaises(SupabaseAuthError) as error:
            await self._resolve(SupabaseAuthError(status_code=503, detail="Supabase недоступен"))
        self.assertEqual(error.exception.status_code, 503)
