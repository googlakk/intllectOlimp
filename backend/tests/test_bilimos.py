import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select

import bilimos_sync
from models import SchoolClass, Student, Teacher, User
from tests.factories import login, make_user

PRIVATE_KEY = Ed25519PrivateKey.generate()
PUBLIC_PEM = PRIVATE_KEY.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
).decode()
SYNC_SECRET = "sync-secret-for-tests"


def roster(students=None, teachers=None):
    return {
        "classes": [
            {"id": "c1", "grade": 7, "letter": "А-12", "name": "7 А-12", "schoolSystem": 12, "program": "cambridge"},
            {"id": "c2", "grade": 7, "letter": "А", "name": "7 А", "schoolSystem": 11, "program": "national"},
        ],
        "students": students if students is not None else [
            {"id": "s1", "userId": "u1", "login": "aibek", "lastName": "Исаков", "firstName": "Айбек",
             "middleName": "Маратович", "classId": "c1"},
            {"id": "s2", "userId": None, "login": None, "lastName": "Исаков", "firstName": "Айбек",
             "middleName": "Маратович", "classId": "c2"},
        ],
        "teachers": teachers if teachers is not None else [
            {"id": "t1", "userId": "u2", "login": "petrova", "lastName": "Петрова", "firstName": "Марина",
             "middleName": None},
        ],
    }


@pytest.fixture
def bilimos(monkeypatch):
    monkeypatch.setenv("BILIMOS_URL", "http://bilimos.test")
    monkeypatch.setenv("OLIMP_ROSTER_KEY", "roster-key")
    monkeypatch.setenv("OLIMP_SYNC_SECRET", SYNC_SECRET)
    monkeypatch.setenv("OLIMP_SSO_PUBLIC_KEY", PUBLIC_PEM)
    state = {"roster": roster(), "calls": 0}

    async def fake_fetch():
        state["calls"] += 1
        return state["roster"]

    monkeypatch.setattr(bilimos_sync, "fetch_roster", fake_fetch)
    return state


def token(sub="u1", role="student", key=PRIVATE_KEY, **overrides):
    now = int(time.time())
    claims = {"iss": "bilimos", "aud": "olimp", "sub": sub, "role": role, "jti": str(uuid.uuid4()),
              "iat": now, "exp": now + 60} | overrides
    return jwt.encode(claims, key, algorithm="EdDSA")


async def sso(client, value):
    return await client.post("/api/sso/bilimos", data={"token": value})


async def users_by_ext(db):
    db.expire_all()
    return {u.external_id: u for u in await db.scalars(select(User).where(User.external_id.is_not(None)))}


# --- sync ---

async def test_sync_upserts_classes_people_and_is_idempotent(db, bilimos):
    await make_user(db, "student", "Айбек Исаков")  # local user holding login aybek.isakov
    for _ in range(2):
        stats = await bilimos_sync.sync_now()
    assert stats == {"classes": 2, "teachers": 1, "students": 2, "deactivated": 0}

    users = await users_by_ext(db)
    assert set(users) == {"u1", "u2"}
    student_user = users["u1"]
    assert student_user.login == "aibek" and student_user.role == "student"
    assert student_user.full_name == "Исаков Айбек Маратович"
    assert student_user.password_hash is None and student_user.must_change_password is False
    assert users["u2"].full_name == "Петрова Марина" and users["u2"].role == "teacher"

    classes = {c.external_id: c for c in await db.scalars(select(SchoolClass))}
    assert classes["c1"].letter == "А-12" and classes["c1"].school_system == 12
    students = {s.external_id: s for s in await db.scalars(select(Student).where(Student.external_id.is_not(None)))}
    assert students["s1"].user_id == student_user.id and students["s1"].class_id == classes["c1"].id
    assert students["s2"].user_id is None and students["s2"].name == students["s1"].name  # same name allowed
    teacher = await db.scalar(select(Teacher).where(Teacher.external_id == "t1"))
    assert teacher.user_id == users["u2"].id
    assert len((await db.scalars(select(User))).all()) == 3


async def test_sync_deactivates_missing_and_reactivates_returning(db, bilimos):
    await bilimos_sync.sync_now()
    bilimos["roster"] = roster(teachers=[])
    stats = await bilimos_sync.sync_now()
    assert stats["deactivated"] == 1
    users = await users_by_ext(db)
    assert users["u2"].is_active is False and users["u1"].is_active is True
    assert await db.scalar(select(Teacher).where(Teacher.external_id == "t1")) is not None  # never deleted

    bilimos["roster"] = roster()
    await bilimos_sync.sync_now()
    assert (await users_by_ext(db))["u2"].is_active is True


async def test_bilimos_login_collision_gets_suffix(db, bilimos):
    local = await make_user(db, "admin", "x")
    local.login = "Aibek"
    await db.commit()
    await bilimos_sync.sync_now()
    assert (await users_by_ext(db))["u1"].login == "aibek2"


async def test_sync_signal_checks_secret(client, db, bilimos, monkeypatch):
    calls = []
    monkeypatch.setattr(bilimos_sync, "request_sync", lambda: calls.append(1))
    url = "/api/integrations/bilimos/sync"
    assert (await client.post(url)).status_code == 401
    assert (await client.post(url, headers={"Authorization": "Bearer wrong"})).status_code == 401
    response = await client.post(url, headers={"Authorization": f"Bearer {SYNC_SECRET}"})
    assert response.status_code == 202 and calls == [1]


async def test_sync_signal_disabled_without_env(client, db):
    assert (await client.post("/api/integrations/bilimos/sync")).status_code == 404


async def test_signals_coalesce(db, bilimos, monkeypatch):
    import asyncio

    started = asyncio.Event()
    release = asyncio.Event()
    runs = []

    async def slow_sync():
        runs.append(1)
        started.set()
        await release.wait()

    monkeypatch.setattr(bilimos_sync, "sync_now", slow_sync)
    bilimos_sync.request_sync()
    await started.wait()
    for _ in range(5):
        bilimos_sync.request_sync()
    release.set()
    await bilimos_sync._worker
    assert len(runs) == 2


async def test_sync_now_is_admin_only(client, db, bilimos):
    teacher = await make_user(db, "teacher", "Елена Сидорова")
    await login(client, teacher)
    assert (await client.post("/api/integrations/bilimos/sync-now")).status_code == 403
    admin = await make_user(db, "admin", "Админ Школы")
    await login(client, admin)
    response = await client.post("/api/integrations/bilimos/sync-now")
    assert response.status_code == 200 and response.json()["students"] == 2


async def test_bilimos_class_is_read_only(client, db, bilimos):
    await bilimos_sync.sync_now()
    admin = await make_user(db, "admin", "Админ Школы")
    await login(client, admin)
    classes = (await client.get("/api/classes")).json()
    synced = next(c for c in classes if c["source"] == "bilimos")
    assert (await client.delete(f"/api/classes/{synced['id']}")).status_code == 409
    student = next(s for s in (await client.get("/api/students")).json() if s["source"] == "bilimos")
    response = await client.put(f"/api/students/{student['id']}/class", json={"class_id": None})
    assert response.status_code == 409


# --- SSO ---

async def test_sso_valid_token_logs_in(client, db, bilimos):
    await bilimos_sync.sync_now()
    response = await sso(client, token())
    assert response.status_code == 303 and response.headers["location"] == "/"
    assert response.headers["referrer-policy"] == "no-referrer"
    me = await client.get("/api/auth/me")
    assert me.status_code == 200 and me.json()["login"] == "aibek"


async def test_sso_unknown_user_triggers_one_sync(client, db, bilimos):
    response = await sso(client, token(sub="u2", role="teacher"))
    assert response.status_code == 303 and bilimos["calls"] == 1


@pytest.mark.parametrize("make_token", [
    lambda: token(key=Ed25519PrivateKey.generate()),
    lambda: token(aud="other"),
    lambda: token(iss="someone"),
    lambda: token(iat=int(time.time()) - 200, exp=int(time.time()) - 100),
    lambda: token(role="teacher"),
    lambda: jwt.encode({"iss": "bilimos", "aud": "olimp", "sub": "u1", "role": "student", "jti": "x",
                        "iat": int(time.time()), "exp": int(time.time()) + 60}, "k" * 32, algorithm="HS256"),
    lambda: "garbage",
])
async def test_sso_rejects_bad_tokens(client, db, bilimos, make_token):
    await bilimos_sync.sync_now()
    response = await sso(client, make_token())
    assert response.status_code == 403
    assert "Нет доступа к платформе" in response.text
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_sso_rejects_replayed_jti(client, db, bilimos):
    await bilimos_sync.sync_now()
    value = token()
    assert (await sso(client, value)).status_code == 303
    await client.post("/api/auth/logout")
    assert (await sso(client, value)).status_code == 403


async def test_sso_rejects_unknown_and_inactive_user(client, db, bilimos):
    await bilimos_sync.sync_now()
    assert (await sso(client, token(sub="nobody"))).status_code == 403
    bilimos["roster"] = roster(students=[])
    await bilimos_sync.sync_now()
    assert (await sso(client, token(sub="u1"))).status_code == 403
