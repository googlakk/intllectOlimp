from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from routes.http_errors import raise_http_error
from services.auth import AuthServiceError, list_login_users, login_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginInput(BaseModel):
    role: str
    name: str


@router.get("/users")
async def users(db: AsyncSession = Depends(get_db)):
    try:
        return await list_login_users(db)
    except AuthServiceError as exc:
        raise_http_error(exc)


@router.post("/login")
async def login(payload: LoginInput, db: AsyncSession = Depends(get_db)):
    try:
        return await login_user(payload.role, payload.name, db)
    except AuthServiceError as exc:
        raise_http_error(exc)
