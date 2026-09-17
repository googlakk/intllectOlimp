from sqlalchemy import func, select

from database import AsyncSessionLocal
from models import Student, Teacher

STUDENTS = ["Айбек Исаков", "Нурай Токтосунова", "Данияр Жумабеков", "Алтынай Сагынбаева", "Тимур Бакиров"]
TEACHERS = ["Марина Петрова", "Елена Сидорова"]


async def seed_if_empty() -> None:
    async with AsyncSessionLocal() as session:
        if (await session.scalar(select(func.count(Student.id)))) == 0:
            session.add_all([Student(name=name, grade=7) for name in STUDENTS])
        if (await session.scalar(select(func.count(Teacher.id)))) == 0:
            session.add_all([Teacher(name=name, subject_id=None) for name in TEACHERS])
        await session.commit()