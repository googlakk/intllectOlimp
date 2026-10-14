import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from models import Classroom, Profile
from routes.accounts import BulkStudentAccountInput, StudentAccountInput, PasswordResetInput
from routes.auth import LoginInput, ChangePasswordInput
from pydantic import ValidationError
from services import accounts
from services.auth import AuthServiceError
from services.student_credentials import generated_student_login, student_temporary_password, validate_temporary_password
from services.supabase_auth import SupabaseAuthError
from test_auth_dependencies import principal


def profile(pid=4):
    return Profile(id=pid, student_id=pid + 5, organization_id=1, auth_user_id=UUID(int=pid),
                   role="student", status="active", login_name=f"student{pid}",
                   display_name=f"Student {pid}", must_change_password=False)


def session(rows):
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = rows
    db.scalars = AsyncMock(return_value=result)
    db.get = AsyncMock(side_effect=lambda model, pid, **kwargs: next((row for row in rows if row.id == pid), None))
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.flush = AsyncMock()
    return db


def classroom():
    return Classroom(id=7, organization_id=1, grade=7, status="active")


class StudentCredentialTests(unittest.IsolatedAsyncioTestCase):
    def test_short_temporary_password_can_sign_in(self):
        self.assertEqual(LoginInput(login="student", password="123456").password, "123456")
        with self.assertRaises(ValidationError):
            LoginInput(login="student", password="12345")
        with self.assertRaises(ValidationError):
            ChangePasswordInput(new_password="123456")

    def test_short_generated_password_and_login(self):
        passwords = {student_temporary_password() for _ in range(100)}
        self.assertGreater(len(passwords), 90)
        for password in passwords:
            self.assertEqual(len(password), 8)
            self.assertTrue(any(char.islower() for char in password))
            self.assertTrue(any(char.isupper() for char in password))
            self.assertTrue(any(char.isdigit() for char in password))
            self.assertFalse(set(password) & set("0O1Ilio"))
        self.assertTrue(generated_student_login(1, 7).startswith("s1c7-"))

    def test_simple_password_limits_and_name_only_input(self):
        self.assertEqual(validate_temporary_password("123456"), "123456")
        self.assertIsNone(validate_temporary_password(None))
        for value in ("12345", "123 456", "123456\n", "x" * 129):
            with self.assertRaises(AuthServiceError):
                validate_temporary_password(value)
        self.assertIsNone(StudentAccountInput(classroom_id=7, display_name="Иван Иванов").login)
        self.assertEqual(len(BulkStudentAccountInput(classroom_id=7, students=[{"display_name": "Иван Иванов"}]).students), 1)
        self.assertIsNone(PasswordResetInput().temporary_password)

    async def test_entire_selection_authorized_before_external_updates(self):
        db = session([profile()])
        with patch.object(accounts, "require_classroom_management", AsyncMock(return_value=classroom())), patch.object(accounts, "admin_update_auth_user", AsyncMock()) as auth:
            with self.assertRaises(AuthServiceError):
                await accounts.reset_classroom_passwords(principal(role="teacher"), 7, db, profile_ids=[4, 99])
        auth.assert_not_awaited()
        db.commit.assert_not_awaited()

    async def test_class_manual_password_or_unique_automatic_passwords(self):
        rows = [profile(4), profile(5)]
        db = session(rows)
        with patch.object(accounts, "require_classroom_management", AsyncMock(return_value=classroom())), patch.object(accounts, "admin_update_auth_user", AsyncMock()) as auth, patch.object(accounts, "forget_principal"):
            result = await accounts.reset_classroom_passwords(principal(role="teacher"), 7, db, temporary_password="123456")
            self.assertEqual(len(result["updated"]), 2)
            self.assertEqual(result["errors"], [])
            self.assertTrue(all(row["temporary_password"] == "123456" for row in result["updated"]))
            self.assertTrue(all(row.must_change_password for row in rows))
            self.assertEqual(auth.await_count, 2)
            result = await accounts.reset_classroom_passwords(principal(role="teacher"), 7, db)
            self.assertNotEqual(result["updated"][0]["temporary_password"], result["updated"][1]["temporary_password"])

    async def test_partial_failure_sanitizes_provider_error(self):
        db = session([profile(4), profile(5)])
        with patch.object(accounts, "require_classroom_management", AsyncMock(return_value=classroom())), patch.object(accounts, "admin_update_auth_user", AsyncMock(side_effect=[SupabaseAuthError(422, "SECRET rejected"), {}])), patch.object(accounts, "forget_principal"):
            result = await accounts.reset_classroom_passwords(principal(role="admin"), 7, db, temporary_password="123456")
        self.assertEqual(result["updated"][0]["profile_id"], 5)
        self.assertEqual(result["errors"][0]["profile_id"], 4)
        self.assertNotIn("SECRET", result["errors"][0]["error"])

    async def test_flag_failure_leaves_auth_unchanged(self):
        row = profile()
        db = session([row])
        db.commit.side_effect = RuntimeError("DB unavailable")
        with patch.object(accounts, "admin_update_auth_user", AsyncMock()) as auth:
            with self.assertRaises(RuntimeError):
                await accounts._issue_temporary_password(principal(role="admin"), row, db, "123456")
        auth.assert_not_awaited()

    async def test_audit_failure_still_returns_changed_credential(self):
        row = profile()
        db = session([row])
        db.commit.side_effect = [None, RuntimeError("DB audit unavailable")]
        with patch.object(accounts, "admin_update_auth_user", AsyncMock()), patch.object(accounts, "forget_principal") as forget:
            self.assertEqual(await accounts._issue_temporary_password(principal(role="admin"), row, db, "123456"), "123456")
        self.assertTrue(row.must_change_password)
        forget.assert_called_with(row.auth_user_id)
        self.assertTrue(all(call.args[0].metadata_json == {} for call in db.add.call_args_list))

    async def test_single_student_custom_and_teacher_strong_default(self):
        row = profile()
        db = session([row])
        with patch.object(accounts, "admin_update_auth_user", AsyncMock()), patch.object(accounts, "forget_principal"):
            self.assertEqual(await accounts.reset_temporary_password(principal(role="admin"), target_profile_id=4, db=db, temporary_password="123456"), "123456")
            row.role, row.student_id = "teacher", None
            self.assertEqual(len(await accounts.reset_temporary_password(principal(role="admin"), target_profile_id=4, db=db)), 14)

    async def test_empty_selection_or_unauthorized_class(self):
        db = session([])
        with patch.object(accounts, "admin_update_auth_user", AsyncMock()) as auth:
            with self.assertRaises(AuthServiceError):
                await accounts.reset_classroom_passwords(principal(role="admin"), 7, db, profile_ids=[])
            with patch.object(accounts, "require_classroom_management", AsyncMock(side_effect=AuthServiceError(403, "Denied"))):
                with self.assertRaises(AuthServiceError):
                    await accounts.reset_classroom_passwords(principal(role="teacher"), 7, db)
        auth.assert_not_awaited()

    async def test_teacher_and_foreign_tenant_target_denied(self):
        row = profile()
        row.role, row.student_id = "teacher", None
        db = session([row])
        with patch.object(accounts, "admin_update_auth_user", AsyncMock()) as auth:
            with self.assertRaises(AuthServiceError):
                await accounts.reset_temporary_password(principal(role="teacher"), target_profile_id=4, db=db)
            row.organization_id = 9
            with self.assertRaises(AuthServiceError):
                await accounts.reset_temporary_password(principal(role="admin"), target_profile_id=4, db=db)
        auth.assert_not_awaited()

    async def test_generated_login_retries_collision_and_returns_name(self):
        db = session([])
        created = profile()
        factory = AsyncMock(side_effect=[AuthServiceError(409, "Duplicate"), (created, "Abcdef23", "auth-id")])
        with patch.object(accounts, "require_classroom_management", AsyncMock(return_value=classroom())), patch.object(accounts, "generated_student_login", side_effect=["s1c7-first2", "s1c7-next23"]), patch.object(accounts, "_create_profile_with_auth", factory):
            result = await accounts.create_student_account(principal(role="admin"), classroom_id=7, display_name="Student", db=db)
        self.assertEqual(factory.await_count, 2)
        self.assertEqual(result["display_name"], created.display_name)
        self.assertEqual(result["temporary_password"], "Abcdef23")

    async def test_explicit_login_not_replaced_on_conflict(self):
        db = session([])
        with patch.object(accounts, "require_classroom_management", AsyncMock(return_value=classroom())), patch.object(accounts, "_create_profile_with_auth", AsyncMock(side_effect=AuthServiceError(409, "Duplicate"))) as factory:
            with self.assertRaises(AuthServiceError):
                await accounts.create_student_account(principal(role="admin"), classroom_id=7, display_name="Student", login="chosen.login", db=db)
        factory.assert_awaited_once()

    async def test_auth_collision_is_retryable_and_policy_errors_are_safe(self):
        for status, detail, expected in ((422, "User already registered", 409), (422, "SECRET password rejected", 422)):
            db = session([])
            db.scalar = AsyncMock(return_value=None)
            with patch.object(accounts, "admin_create_auth_user", AsyncMock(side_effect=SupabaseAuthError(status, detail))):
                with self.assertRaises(AuthServiceError) as error:
                    await accounts._create_profile_with_auth(user=principal(role="admin"), role="student", login="valid.login", display_name="Student", teacher_id=None, student_id=9, db=db)
            self.assertEqual(error.exception.status_code, expected)
            self.assertNotIn("SECRET", error.exception.detail)
