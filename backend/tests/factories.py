from accounts import unique_login
from models import Student, Teacher, User
from security import hash_password

PASSWORD = "correct-horse-1"


async def make_user(db, role: str, full_name: str, password: str = PASSWORD, **fields) -> User:
    taken = set()
    user = User(
        login=unique_login(full_name, taken),
        full_name=full_name,
        role=role,
        password_hash=hash_password(password),
        **fields,
    )
    db.add(user)
    await db.flush()
    if role == "teacher":
        db.add(Teacher(name=full_name, user_id=user.id))
    elif role == "student":
        db.add(Student(name=full_name, grade=7, user_id=user.id))
    await db.commit()
    return user


async def login(client, user: User, password: str = PASSWORD):
    return await client.post("/api/auth/login", json={"login": user.login, "password": password})
