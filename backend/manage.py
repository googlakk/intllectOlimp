"""Admin command line.

  python manage.py create-admin <login> "<Full Name>"
  python manage.py set-password <login>          # prints a new temporary password
  python manage.py seed-demo                     # demo teachers/students with printed passwords
"""
import asyncio
import sys

from sqlalchemy import func, select

from accounts import unique_login
from database import AsyncSessionLocal, engine
from models import Student, Teacher, User
from security import generate_password, hash_password

DEMO_STUDENTS = ["Айбек Исаков", "Нурай Токтосунова", "Данияр Жумабеков", "Алтынай Сагынбаева", "Тимур Бакиров"]
DEMO_TEACHERS = ["Марина Петрова", "Елена Сидорова"]


async def _taken_logins(session) -> set[str]:
    return set((await session.scalars(select(User.login))).all())


async def create_admin(login: str, full_name: str) -> None:
    async with AsyncSessionLocal() as session:
        if await session.scalar(select(User).where(func.lower(User.login) == login.lower())):
            sys.exit(f"Пользователь {login} уже существует")
        password = generate_password()
        session.add(User(login=login, full_name=full_name, role="admin", password_hash=hash_password(password)))
        await session.commit()
    print(f"Админ создан. Логин: {login}  Временный пароль: {password}")


async def set_password(login: str) -> None:
    async with AsyncSessionLocal() as session:
        user = await session.scalar(select(User).where(func.lower(User.login) == login.lower()))
        if user is None:
            sys.exit(f"Пользователь {login} не найден")
        password = generate_password()
        user.password_hash = hash_password(password)
        user.must_change_password = True
        await session.commit()
    print(f"{user.full_name}: логин {user.login}  временный пароль {password}")


async def seed_demo() -> None:
    async with AsyncSessionLocal() as session:
        taken = await _taken_logins(session)
        existing = set((await session.scalars(select(User.full_name))).all())
        created = []
        for names, role in ((DEMO_TEACHERS, "teacher"), (DEMO_STUDENTS, "student")):
            for name in names:
                if name in existing:
                    continue
                password = generate_password()
                user = User(login=unique_login(name, taken), full_name=name, role=role, password_hash=hash_password(password))
                session.add(user)
                await session.flush()
                session.add(Teacher(name=name, user_id=user.id) if role == "teacher" else Student(name=name, grade=7, user_id=user.id))
                created.append((role, name, user.login, password))
        await session.commit()
    for role, name, login, password in created:
        print(f"{role:8} {name:22} {login:22} {password}")
    if not created:
        print("Демо-пользователи уже есть")


async def main(argv: list[str]) -> None:
    try:
        match argv:
            case ["create-admin", login, full_name]:
                await create_admin(login, full_name)
            case ["set-password", login]:
                await set_password(login)
            case ["seed-demo"]:
                await seed_demo()
            case _:
                sys.exit(__doc__)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
