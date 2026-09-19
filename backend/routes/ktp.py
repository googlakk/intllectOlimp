from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Section, Subject, Topic

router = APIRouter(prefix="/api/ktp", tags=["ktp"])


class TopicInput(BaseModel):
    ktp_number: str = ""          # у «Контрольной работы» номера в КТП нет
    name: str = Field(min_length=1)
    hours: int = Field(default=1, ge=0)
    lesson_type: Literal["study", "assessment", "project"] = "study"
    learning_objectives: str = ""
    skills: list[str] = Field(default_factory=list)
    resources: str = ""


class SectionInput(BaseModel):
    name: str = Field(min_length=1)
    total_hours: int = Field(ge=0)
    topics: list[TopicInput] = Field(default_factory=list)


class KtpUploadInput(BaseModel):
    subject_name: str = Field(min_length=1)
    grade: int = Field(ge=1, le=12)
    hours_per_week: float = Field(ge=0)
    hours_per_year: int = Field(ge=0)
    instruction_language: Literal["ru", "ky"] = "ru"
    sections: list[SectionInput] = Field(default_factory=list)


@router.post("/upload")
async def upload_ktp(payload: KtpUploadInput, db: AsyncSession = Depends(get_db)):
    try:
        subject = Subject(
            name=payload.subject_name,
            grade=payload.grade,
            hours_per_week=payload.hours_per_week,
            hours_per_year=payload.hours_per_year,
            source_info="Загружено из КТП",
            instruction_language=payload.instruction_language,
        )
        db.add(subject)
        await db.flush()

        topic_count = 0
        for sort_order, section_input in enumerate(payload.sections, start=1):
            section = Section(
                subject_id=subject.id,
                name=section_input.name,
                sort_order=sort_order,
                total_hours=section_input.total_hours,
            )
            db.add(section)
            await db.flush()

            for topic_order, topic_input in enumerate(section_input.topics, start=1):
                db.add(
                    Topic(
                        section_id=section.id,
                        sort_order=topic_order,
                        ktp_number=topic_input.ktp_number,
                        name=topic_input.name,
                        hours=topic_input.hours,
                        lesson_type=topic_input.lesson_type,
                        learning_objectives=topic_input.learning_objectives,
                        skills=topic_input.skills,
                        resources=topic_input.resources,
                    )
                )
                topic_count += 1

        await db.commit()
        await db.refresh(subject)
        return {
            "id": subject.id,
            "name": subject.name,
            "grade": subject.grade,
            "hours_per_week": subject.hours_per_week,
            "hours_per_year": subject.hours_per_year,
            "source_info": subject.source_info,
            "instruction_language": subject.instruction_language,
            "created_at": subject.created_at,
            "section_count": len(payload.sections),
            "topic_count": topic_count,
        }
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Не удалось сохранить загруженный КТП") from exc

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIXES = (".docx", ".pdf")


@router.post("/parse")
async def parse_ktp(file: UploadFile = File(...)):
    """Разбирает файл КТП и возвращает ЧЕРНОВИК. В базу ничего не пишет.

    Черновик проверяет и правит учитель, после чего отправляет на /api/ktp/upload.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise HTTPException(
            status_code=422,
            detail="Поддерживаются только файлы .docx и .pdf",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Файл пустой")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Файл больше {MAX_UPLOAD_BYTES // (1024 * 1024)} МБ",
        )

    from ktp.extract import extract
    from ktp.mapper import map_to_schema

    try:
        extraction = extract(data, filename)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Не удалось прочитать файл: {exc}") from exc

    if not extraction.tables:
        raise HTTPException(
            status_code=422,
            detail="В файле не найдено таблиц. Убедитесь, что КТП оформлен таблицей, "
                   "а не картинкой или сканом.",
        )

    try:
        draft = await map_to_schema(extraction)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Сбой разбора: {exc}") from exc

    topics = [t for section in draft.get("sections") or [] for t in (section.get("topics") or [])]
    draft["source"] = {
        "filename": filename,
        "kind": extraction.source_kind,
        "table_count": len(extraction.tables),
        "row_count": extraction.row_count,
    }
    draft["stats"] = {
        "section_count": len(draft.get("sections") or []),
        "topic_count": len(topics),
        "low_confidence_count": sum(1 for t in topics if t.get("confidence") == "low"),
        "with_objectives": sum(1 for t in topics if (t.get("learning_objectives") or "").strip()),
    }
    return draft
