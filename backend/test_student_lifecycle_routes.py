import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from auth_dependencies import get_current_user
from database import get_db
from errors import ApplicationError
from routes.accounts import router
from services.auth import AuthServiceError
from test_auth_dependencies import principal


class StudentLifecycleRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.user = principal(role="admin")
        self.db = MagicMock()
        async def current_user():
            return self.user

        async def session():
            return self.db

        self.app.dependency_overrides[get_current_user] = current_user
        self.app.dependency_overrides[get_db] = session

        @self.app.exception_handler(ApplicationError)
        async def map_error(request, error):
            return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    async def request(self, method, url, **kwargs):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test") as client:
            return await client.request(method, url, **kwargs)

    async def test_delete_has_explicit_class_and_profile_and_restores_to_selected_class(self):
        with patch("routes.accounts.remove_student", new=AsyncMock()) as remove:
            response = await self.request("DELETE", "/api/accounts/classrooms/7/students/4")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        remove.assert_awaited_once_with(self.user, classroom_id=7, student_profile_id=4, db=self.db)
        with patch("routes.accounts.restore_student", new=AsyncMock()) as restore:
            response = await self.request("POST", "/api/accounts/students/4/restore", json={"target_classroom_id": 8})
        self.assertEqual(response.status_code, 200)
        restore.assert_awaited_once_with(self.user, student_profile_id=4, target_classroom_id=8, db=self.db)

    async def test_teacher_cannot_call_lifecycle_endpoints(self):
        self.user = principal(role="teacher")
        with (
            patch("routes.accounts.remove_student", new=AsyncMock()) as remove,
            patch("routes.accounts.restore_student", new=AsyncMock()) as restore,
            patch("routes.accounts.list_removed_students", new=AsyncMock()) as listing,
        ):
            for method, path, kwargs in (
                ("DELETE", "/api/accounts/classrooms/7/students/4", {}),
                ("POST", "/api/accounts/students/4/restore", {"json": {"target_classroom_id": 8}}),
                ("GET", "/api/accounts/students/archived", {}),
            ):
                response = await self.request(method, path, **kwargs)
                self.assertEqual(response.status_code, 403)
            remove.assert_not_awaited()
            restore.assert_not_awaited()
            listing.assert_not_awaited()

    async def test_archive_list_and_domain_errors_use_existing_http_mapping(self):
        with patch("routes.accounts.list_removed_students", new=AsyncMock(return_value=[])):
            response = await self.request("GET", "/api/accounts/students/archived")
        self.assertEqual(response.json(), [])
        with patch("routes.accounts.remove_student", new=AsyncMock(side_effect=AuthServiceError(409, "Обновите список."))):
            response = await self.request("DELETE", "/api/accounts/classrooms/7/students/4")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "Обновите список."})
