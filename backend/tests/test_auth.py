import pytest

from security import SESSION_COOKIE
from tests.factories import PASSWORD, login, make_user


async def test_login_sets_httponly_cookie_and_me_works(client, db):
    user = await make_user(db, "student", "Айбек Исаков")
    response = await login(client, user)
    assert response.status_code == 200
    body = response.json()
    assert body["login"] == "aybek.isakov"
    assert body["role"] == "student"
    assert body["student_id"] is not None
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "password_hash" not in body

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == user.id


async def test_login_is_case_insensitive(client, db):
    user = await make_user(db, "teacher", "Марина Петрова")
    response = await client.post("/api/auth/login", json={"login": "Marina.Petrova ", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["login"] == user.login


@pytest.mark.parametrize("login_value,password", [("aybek.isakov", "wrong"), ("nobody", PASSWORD)])
async def test_bad_credentials_get_same_error(client, db, login_value, password):
    await make_user(db, "student", "Айбек Исаков")
    response = await client.post("/api/auth/login", json={"login": login_value, "password": password})
    assert response.status_code == 401
    assert response.json()["detail"] == "Неверный логин или пароль"


async def test_user_without_password_cannot_login(client, db):
    user = await make_user(db, "student", "Нурай Токтосунова")
    user.password_hash = None
    await db.commit()
    assert (await login(client, user)).status_code == 401


async def test_inactive_user_cannot_login_or_use_session(client, db):
    user = await make_user(db, "student", "Данияр Жумабеков")
    assert (await login(client, user)).status_code == 200
    user.is_active = False
    await db.commit()
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await login(client, user)).status_code == 401


async def test_logout_clears_session(client, db):
    user = await make_user(db, "student", "Тимур Бакиров")
    await login(client, user)
    assert (await client.post("/api/auth/logout")).status_code == 204
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_tampered_cookie_rejected(client):
    client.cookies.set(SESSION_COOKIE, "not-a-token")
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_change_password(client, db):
    user = await make_user(db, "student", "Алтынай Сагынбаева")
    await login(client, user)
    assert user.must_change_password is True

    wrong = await client.post("/api/auth/change-password", json={"current_password": "x", "new_password": "new-password-1"})
    assert wrong.status_code == 400
    short = await client.post("/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "short"})
    assert short.status_code == 422

    ok = await client.post("/api/auth/change-password", json={"current_password": PASSWORD, "new_password": "new-password-1"})
    assert ok.status_code == 200
    assert ok.json()["must_change_password"] is False
    await client.post("/api/auth/logout")
    assert (await login(client, user)).status_code == 401
    assert (await login(client, user, "new-password-1")).status_code == 200


async def test_users_listing_endpoint_removed(client):
    assert (await client.get("/api/auth/users")).status_code in (404, 405)
