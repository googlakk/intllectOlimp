from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from auth_dependencies import require_roles
from database import get_db
from services.auth import AuthPrincipal
from services.textbooks import create_textbook, get_textbook, list_textbooks, process_textbook

router = APIRouter(prefix="/api/textbooks", tags=["textbooks"])


class TextbookCreateInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    grade: int = Field(ge=1, le=11)
    subject_id: int | None = Field(default=None, ge=1)
    language: str = Field(default="ru", pattern="^(ru|ky)$")
    authors: str | None = Field(default=None, max_length=300)
    year: int | None = Field(default=None, ge=1950, le=2100)
    file_name: str = Field(min_length=1, max_length=255)
    file_size: int = Field(ge=1)


@router.get("")
async def textbooks(user: AuthPrincipal = Depends(require_roles("admin", "teacher")), db: AsyncSession = Depends(get_db)):
    return await list_textbooks(db, user=user)


@router.post("")
async def create(payload: TextbookCreateInput, user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
                 db: AsyncSession = Depends(get_db)):
    return await create_textbook(payload.model_dump(), db, user=user)


@router.post("/{textbook_id}/process")
async def process(textbook_id: int, user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
                  db: AsyncSession = Depends(get_db)):
    return await process_textbook(textbook_id, db, user=user)


@router.get("/{textbook_id}")
async def textbook(textbook_id: int, user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
                   db: AsyncSession = Depends(get_db)):
    return await get_textbook(textbook_id, db, user=user)
