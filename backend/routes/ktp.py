from typing import Literal

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from languages import Language
from topic_semantics import LessonType
from ktp.parsing import KtpParseError, parse_ktp_draft
from ktp.persistence import KtpPersistenceError, save_ktp_draft
from routes.http_errors import raise_http_error
from auth_dependencies import require_roles
from services.auth import AuthPrincipal
from services.educator_access import require_grade_management

router = APIRouter(prefix="/api/ktp", tags=["ktp"])


class TopicInput(BaseModel):
    ktp_number: str = ""          # у «Контрольной работы» номера в КТП нет
    name: str = Field(min_length=1)
    hours: int = Field(default=1, ge=0)
    lesson_type: LessonType = "study"
    learning_objectives: str = ""
    skills: list[str] = Field(default_factory=list)
    resources: str = ""
    review_required: bool = False


class SectionInput(BaseModel):
    name: str = Field(min_length=1)
    total_hours: int = Field(ge=0)
    topics: list[TopicInput] = Field(default_factory=list)


class KtpUploadInput(BaseModel):
    subject_name: str = Field(min_length=1)
    grade: int = Field(ge=1, le=12)
    hours_per_week: float = Field(ge=0)
    hours_per_year: int = Field(ge=0)
    instruction_language: Language = "ru"
    sections: list[SectionInput] = Field(default_factory=list)


@router.post("/upload")
async def upload_ktp(
    payload: KtpUploadInput,
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    await require_grade_management(user, payload.grade, db)
    try:
        return await save_ktp_draft(payload, db)
    except KtpPersistenceError as exc:
        raise_http_error(exc)


@router.post("/parse")
async def parse_ktp(file: UploadFile = File(...), user: AuthPrincipal = Depends(require_roles("admin"))):
    """Разбирает файл КТП и возвращает ЧЕРНОВИК. В базу ничего не пишет.

    Черновик проверяет и правит учитель, после чего отправляет на /api/ktp/upload.
    """
    filename = file.filename or ""
    data = await file.read()
    try:
        return await parse_ktp_draft(filename=filename, data=data)
    except KtpParseError as exc:
        raise_http_error(exc)
