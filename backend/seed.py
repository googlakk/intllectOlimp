from sqlalchemy import func, select

from database import AsyncSessionLocal
from models import Student, Teacher

STUDENTS = ["Айбек Исаков", "Нурай Токтосунова", "Данияр Жумабеков", "Алтынай Сагынбаева", "Тимур Бакиров"]
TEACHERS = ["Марина Петрова", "Елена Сидорова"]


async def seed_if_empty() -> None:
    async with AsyncSessionLocal() as session:
        # Оба счётчика одним запросом; запись — только если база действительно пустая.
        students, teachers = (await session.execute(select(
            select(func.count(Student.id)).scalar_subquery(),
            select(func.count(Teacher.id)).scalar_subquery(),
        ))).one()
        if students == 0:
            session.add_all([Student(name=name, grade=7) for name in STUDENTS])
        if teachers == 0:
            session.add_all([Teacher(name=name, subject_id=None) for name in TEACHERS])
        if students == 0 or teachers == 0:
            await session.commit()