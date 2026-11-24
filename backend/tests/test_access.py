import pytest

from tests.factories import login, make_user

PROTECTED = [
    ("get", "/api/subjects"),
    ("get", "/api/dashboard/overview"),
    ("get", "/api/components"),
    ("post", "/api/ktp/upload"),
    ("post", "/api/lessons/generate"),
    ("get", "/api/lessons/1"),
    ("put", "/api/lessons/1/publish"),
    ("delete", "/api/lessons/1"),
    ("post", "/api/progress"),
    ("get", "/api/progress/me"),
    ("get", "/api/progress/1"),
]

STAFF_ONLY = [
    ("get", "/api/dashboard/overview"),
    ("get", "/api/dashboard/students"),
    ("get", "/api/components"),
    ("post", "/api/ktp/upload"),
    ("post", "/api/lessons/generate"),
    ("put", "/api/lessons/1/blocks"),
    ("get", "/api/lessons/1/quality"),
    ("put", "/api/lessons/1/publish"),
    ("put", "/api/lessons/1/unpublish"),
    ("delete", "/api/lessons/1"),
    ("get", "/api/progress/1"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
async def test_anonymous_gets_401(client, method, path):
    response = await client.request(method, path, json={})
    assert response.status_code == 401, path


@pytest.mark.parametrize("method,path", STAFF_ONLY)
async def test_student_gets_403_on_staff_endpoints(client, db, method, path):
    student = await make_user(db, "student", "Айбек Исаков")
    await login(client, student)
    response = await client.request(method, path, json={"blocks": [], "topic_id": 1})
    assert response.status_code == 403, path


async def test_teacher_cannot_save_student_progress(client, db):
    teacher = await make_user(db, "teacher", "Марина Петрова")
    await login(client, teacher)
    response = await client.post("/api/progress", json={"topic_id": 1})
    assert response.status_code == 403


async def test_student_reads_only_own_progress(client, db):
    student = await make_user(db, "student", "Айбек Исаков")
    await login(client, student)
    assert (await client.get("/api/progress/me")).status_code == 200
    assert (await client.get("/api/subjects")).status_code == 200
