import unittest
from types import SimpleNamespace

from models import Student, Teacher
from services.auth import AuthServiceError, login_user, serialize_user, user_model_for_role


def run(coro):
    import asyncio

    return asyncio.run(coro)


class FakeSession:
    def __init__(self, user=None):
        self.user = user

    async def scalar(self, _statement):
        return self.user


class AuthServiceTests(unittest.TestCase):
    def test_student_and_teacher_are_serialized_to_same_user_shape(self):
        student = SimpleNamespace(id=1, name="Алина", grade=7)
        teacher = SimpleNamespace(id=2, name="Учитель")

        self.assertEqual(
            serialize_user(student, "student"),
            {"id": 1, "name": "Алина", "role": "student", "grade": 7},
        )
        self.assertEqual(
            serialize_user(teacher, "teacher"),
            {"id": 2, "name": "Учитель", "role": "teacher", "grade": None},
        )

    def test_role_selects_expected_model(self):
        self.assertIs(user_model_for_role("student"), Student)
        self.assertIs(user_model_for_role("teacher"), Teacher)

    def test_unknown_role_is_rejected(self):
        with self.assertRaises(AuthServiceError) as ctx:
            user_model_for_role("admin")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "Неизвестная роль")

    def test_login_returns_serialized_user(self):
        user = SimpleNamespace(id=5, name="Алина", grade=8)

        self.assertEqual(
            run(login_user("student", "Алина", FakeSession(user))),
            {"id": 5, "name": "Алина", "role": "student", "grade": 8},
        )

    def test_login_reports_missing_user(self):
        with self.assertRaises(AuthServiceError) as ctx:
            run(login_user("teacher", "Нет такого", FakeSession(None)))

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Пользователь не найден")


if __name__ == "__main__":
    unittest.main()
