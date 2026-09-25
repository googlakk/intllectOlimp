"""Topic editing endpoints; student catalog remains read-only."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from auth_dependencies import require_roles
from database import get_db
from errors import ApplicationError
from routes.http_errors import raise_http_error
from services.auth import AuthPrincipal
from services import topics as service
from topic_semantics import LessonType

router = APIRouter(prefix="/api", tags=["topics"])


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    lesson_type: LessonType = "study"
    hours: int = Field(default=1, ge=0, le=1000)
    learning_objectives: str = ""
    skills: list[str] = Field(default_factory=list)
    covered_topic_ids: list[int] | None = None
    source_assessment_topic_id: int | None = Field(default=None, ge=1)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Введите название темы")
        return value.strip()


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    lesson_type: LessonType | None = None
    hours: int | None = Field(default=None, ge=0, le=1000)
    learning_objectives: str | None = None
    skills: list[str] | None = None
    covered_topic_ids: list[int] | None = None
    source_assessment_topic_id: int | None = Field(default=None, ge=1)

    @field_validator("name", "lesson_type", "hours", "learning_objectives", "skills", "covered_topic_ids")
    @classmethod
    def nonnull_fields(cls, value):
        if value is None:
            raise ValueError("Поле не может быть пустым")
        return value

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value):
        return TopicCreate.nonblank_name(value)


@router.get("/topics/{topic_id}")
async def get_topic(topic_id: int, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    try:
        return await service.get_topic(topic_id, user, db)
    except ApplicationError as exc:
        raise_http_error(exc)


@router.post("/sections/{section_id}/topics", status_code=201)
async def create_topic(section_id: int, payload: TopicCreate, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    try:
        return await service.create_topic(section_id, payload.model_dump(exclude_unset=True), user, db)
    except ApplicationError as exc:
        raise_http_error(exc)


@router.patch("/topics/{topic_id}")
async def update_topic(topic_id: int, payload: TopicUpdate, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    try:
        return await service.update_topic(topic_id, payload.model_dump(exclude_unset=True), user, db)
    except ApplicationError as exc:
        raise_http_error(exc)


@router.post("/topics/{topic_id}/archive")
async def archive_topic(topic_id: int, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    try:
        return await service.set_topic_archived(topic_id, True, user, db)
    except ApplicationError as exc:
        raise_http_error(exc)


@router.post("/topics/{topic_id}/restore")
async def restore_topic(topic_id: int, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    try:
        return await service.set_topic_archived(topic_id, False, user, db)
    except ApplicationError as exc:
        raise_http_error(exc)


class SectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        return TopicCreate.nonblank_name(value)


class CourseCreate(SectionCreate):
    grade: int = Field(ge=1, le=12)


@router.post("/subjects", status_code=201)
async def create_course(payload: CourseCreate, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    from services.course_creation import create_course as create
    try:
        return await create(payload.name, payload.grade, user, db)
    except ApplicationError as exc:
        raise_http_error(exc)


@router.patch("/subjects/{subject_id}")
async def rename_course(subject_id: int, payload: SectionCreate, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    from services.course_creation import rename_subject
    try:
        return await rename_subject(subject_id, payload.name, user, db)
    except ApplicationError as exc:
        raise_http_error(exc)


@router.post("/subjects/{subject_id}/sections", status_code=201)
async def create_section(subject_id: int, payload: SectionCreate, user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    from services.course_creation import create_section as create
    try:
        return await create(subject_id, payload.name, user, db)
    except ApplicationError as exc:
        raise_http_error(exc)
