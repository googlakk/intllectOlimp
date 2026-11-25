"""Roster sync from BilimOs (the source of truth for people and classes).

BilimOs returns a full snapshot of admitted students/teachers. We upsert by
external_id in one transaction; users missing from the snapshot are deactivated
(never deleted, progress stays) and come back active when they return.
Synced users have no password: they sign in only through BilimOs SSO.
"""
import asyncio
import logging
import os

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from accounts import numbered_login, unique_login
from database import AsyncSessionLocal
from models import SchoolClass, Student, Teacher, User

log = logging.getLogger("bilimos")
ROSTER_PATH = "/api/v1/integrations/olimp/roster"


def configured() -> bool:
    return bool(os.getenv("BILIMOS_URL") and os.getenv("OLIMP_ROSTER_KEY"))


async def fetch_roster() -> dict:
    url = os.environ["BILIMOS_URL"].rstrip("/") + ROSTER_PATH
    headers = {"Authorization": f"Bearer {os.environ['OLIMP_ROSTER_KEY']}"}
    async with httpx.AsyncClient(timeout=15) as http:
        response = await http.get(url, headers=headers)
        response.raise_for_status()
        return response.json()


def _full_name(person: dict) -> str:
    return " ".join(p for p in (person.get("lastName"), person.get("firstName"), person.get("middleName")) if p)


async def apply_roster(db: AsyncSession, roster: dict) -> dict:
    """Upsert the snapshot; caller commits."""
    classes = {c.external_id: c for c in await db.scalars(select(SchoolClass).where(SchoolClass.external_id.is_not(None)))}
    for item in roster["classes"]:
        row = classes.get(item["id"])
        if row is None:
            row = classes[item["id"]] = SchoolClass(external_id=item["id"])
            db.add(row)
        row.grade, row.letter = item["grade"], item["letter"]
        row.school_system, row.program = item["schoolSystem"], item["program"]
    await db.flush()

    users = {u.external_id: u for u in await db.scalars(select(User).where(User.external_id.is_not(None)))}
    taken = {login.lower() for login in await db.scalars(select(func.lower(User.login)))}
    seen: set[str] = set()

    async def upsert_user(external_id: str, login: str | None, full_name: str, role: str) -> User:
        seen.add(external_id)
        user = users.get(external_id)
        if user is None:
            new_login = numbered_login(login.strip().lower()[:90], taken) if login else unique_login(full_name, taken)
            user = users[external_id] = User(external_id=external_id, login=new_login)
            db.add(user)
        user.full_name, user.role = full_name, role
        user.password_hash, user.must_change_password, user.is_active = None, False, True
        await db.flush()
        return user

    teachers = {t.external_id: t for t in await db.scalars(select(Teacher).where(Teacher.external_id.is_not(None)))}
    for item in roster["teachers"]:
        name = _full_name(item)
        user = await upsert_user(item["userId"], item["login"], name, "teacher")
        row = teachers.get(item["id"])
        if row is None:
            row = Teacher(external_id=item["id"])
            db.add(row)
        row.name, row.user_id = name, user.id

    students = {s.external_id: s for s in await db.scalars(select(Student).where(Student.external_id.is_not(None)))}
    for item in roster["students"]:
        name = _full_name(item)
        user = await upsert_user(item["userId"], item.get("login"), name, "student") if item.get("userId") else None
        row = students.get(item["id"])
        if row is None:
            row = Student(external_id=item["id"])
            db.add(row)
        school_class = classes.get(item["classId"])
        row.name, row.user_id = name, user.id if user else None
        row.class_id = school_class.id if school_class else None
        row.grade = school_class.grade if school_class else (row.grade or 7)

    deactivated = 0
    for external_id, user in users.items():
        if external_id not in seen and user.is_active:
            user.is_active, deactivated = False, deactivated + 1
    await db.flush()
    return {
        "classes": len(roster["classes"]),
        "teachers": len(roster["teachers"]),
        "students": len(roster["students"]),
        "deactivated": deactivated,
    }


_lock = asyncio.Lock()
_dirty = False
_worker: asyncio.Task | None = None


async def sync_now() -> dict:
    """Fetch and apply the roster now (serialized with any running sync)."""
    async with _lock:
        roster = await fetch_roster()
        async with AsyncSessionLocal() as db:
            stats = await apply_roster(db, roster)
            await db.commit()
    log.info("BilimOs sync: %s", stats)
    return stats


async def _drain() -> None:
    global _dirty
    while _dirty:
        _dirty = False
        try:
            await sync_now()
        except Exception:
            log.exception("BilimOs sync failed")


def request_sync() -> None:
    """Coalesce signals: at most one running sync plus one follow-up."""
    global _dirty, _worker
    if not configured():
        return
    _dirty = True
    if _worker is None or _worker.done():
        _worker = asyncio.create_task(_drain())
