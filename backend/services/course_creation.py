"""Create an empty program without requiring a KTP import."""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from errors import ApplicationError
from languages import LANGUAGE_NAME, normalize_language
from models import Section, Subject
from services.auth import AuthPrincipal
from textbooks.models import Textbook
from services.catalog import clear_subject_outline_cache
from services.educator_access import require_grade_management, require_subject_management


async def create_course(name: str, grade: int, user: AuthPrincipal, db: AsyncSession, instruction_language: str = "ru") -> dict:
    await require_grade_management(user, grade, db)
    subject = Subject(name=name.strip(), grade=grade, hours_per_week=1, hours_per_year=0,
                      instruction_language=normalize_language(instruction_language))
    db.add(subject)
    await db.flush()
    section = Section(subject_id=subject.id, name="Основной раздел", sort_order=1, total_hours=0)
    db.add(section)
    await db.commit()
    await db.refresh(subject)
    return {"id": subject.id, "name": subject.name, "grade": subject.grade,
            "hours_per_week": subject.hours_per_week, "hours_per_year": subject.hours_per_year,
            "source_info": None, "instruction_language": subject.instruction_language}


async def create_section(subject_id: int, name: str, user: AuthPrincipal, db: AsyncSession) -> dict:
    await require_subject_management(user, subject_id, db)
    position = await db.scalar(select(func.max(Section.sort_order)).where(Section.subject_id == subject_id))
    section = Section(subject_id=subject_id, name=name.strip(), sort_order=(position or 0) + 1, total_hours=0)
    db.add(section)
    await db.commit()
    await db.refresh(section)
    clear_subject_outline_cache(subject_id)
    return {"id": section.id, "subject_id": subject_id, "name": section.name,
            "sort_order": section.sort_order, "total_hours": 0}


async def rename_subject(subject_id: int, name: str, user: AuthPrincipal, db: AsyncSession,
                         instruction_language: str | None = None) -> dict:
    subject = await require_subject_management(user, subject_id, db)
    subject.name = name.strip()
    if instruction_language is not None and instruction_language != subject.instruction_language:
        language = normalize_language(instruction_language)
        # Уроки предмета строятся по его учебникам: язык предмета и учебников должен совпадать.
        other = await db.scalar(select(Textbook.language).where(
            Textbook.subject_id == subject_id, Textbook.language != language).limit(1))
        if other is not None:
            raise ApplicationError(409, f"К предмету привязан учебник на языке «{LANGUAGE_NAME.get(other, other)}». "
                                        "Сначала отвяжите его или загрузите учебник на новом языке.")
        subject.instruction_language = language
    await db.commit()
    await db.refresh(subject)
    clear_subject_outline_cache(subject_id)
    return {"id": subject.id, "name": subject.name, "grade": subject.grade,
            "hours_per_week": subject.hours_per_week, "hours_per_year": subject.hours_per_year,
            "source_info": subject.source_info, "instruction_language": subject.instruction_language}
