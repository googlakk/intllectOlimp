from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from auth_dependencies import require_roles
from services.accounts import (
    assign_teacher,
    create_classroom,
    create_student_account,
    create_teacher_account,
    list_classroom_students,
    list_classrooms,
    list_teachers,
    reset_temporary_password,
    set_account_blocked,
    transfer_student,
    unassign_teacher,
)
from services.auth import AuthPrincipal
from services.teacher_assignments import replace_teacher_subjects, teacher_subject_options

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


class ClassroomInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    grade: int = Field(ge=1, le=12)
    academic_year: str = Field(min_length=4, max_length=20)


class AccountInput(BaseModel):
    login: str = Field(min_length=3, max_length=50)
    display_name: str = Field(min_length=2, max_length=255)


class StudentAccountInput(AccountInput):
    classroom_id: int


class TeacherAccountInput(AccountInput):
    subject_ids: list[int] = Field(min_length=1, max_length=200)
    classroom_ids: list[int] = Field(default_factory=list, max_length=200)

    @field_validator("display_name")
    @classmethod
    def teacher_name(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Введите имя учителя (не менее двух символов).")
        return value


class TeacherSubjectsInput(BaseModel):
    subject_ids: list[int] = Field(max_length=200)


class BulkStudentAccountInput(BaseModel):
    classroom_id: int
    students: list[AccountInput] = Field(min_length=1, max_length=100)


class TeacherAssignmentInput(BaseModel):
    teacher_profile_id: int


class TransferInput(BaseModel):
    target_classroom_id: int


@router.get("/classrooms")
async def classrooms(
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    return await list_classrooms(user, db)


@router.post("/classrooms")
async def add_classroom(
    payload: ClassroomInput,
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return await create_classroom(user, **payload.model_dump(), db=db)


@router.post("/teachers")
async def add_teacher(
    payload: TeacherAccountInput,
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return await create_teacher_account(user, **payload.model_dump(), db=db)


@router.get("/teachers")
async def teachers(
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return await list_teachers(user, db)


@router.put("/teachers/{teacher_profile_id}/subjects")
async def update_teacher_subjects(
    teacher_profile_id: int,
    payload: TeacherSubjectsInput,
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    await replace_teacher_subjects(user, teacher_profile_id=teacher_profile_id, subject_ids=payload.subject_ids, db=db)
    return {"ok": True}


@router.get("/teacher-subjects/options")
async def subject_assignment_options(
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    return await teacher_subject_options(user, db)


@router.post("/students")
async def add_student(
    payload: StudentAccountInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    return await create_student_account(user, **payload.model_dump(), db=db)


@router.post("/students/bulk")
async def add_students_bulk(
    payload: BulkStudentAccountInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    created = []
    errors = []
    for index, student in enumerate(payload.students):
        try:
            created.append(await create_student_account(
                user,
                classroom_id=payload.classroom_id,
                login=student.login,
                display_name=student.display_name,
                db=db,
            ))
        except Exception as exc:
            await db.rollback()
            errors.append({"row": index + 1, "login": student.login, "error": str(exc)})
    return {"created": created, "errors": errors}


@router.get("/classrooms/{classroom_id}/students")
async def classroom_students(
    classroom_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    return await list_classroom_students(user, classroom_id, db)


@router.post("/classrooms/{classroom_id}/teachers")
async def add_teacher_to_classroom(
    classroom_id: int,
    payload: TeacherAssignmentInput,
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    await assign_teacher(user, classroom_id=classroom_id, teacher_profile_id=payload.teacher_profile_id, db=db)
    return {"ok": True}


@router.delete("/classrooms/{classroom_id}/teachers/{teacher_profile_id}")
async def remove_teacher_from_classroom(
    classroom_id: int,
    teacher_profile_id: int,
    user: AuthPrincipal = Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    await unassign_teacher(
        user,
        classroom_id=classroom_id,
        teacher_profile_id=teacher_profile_id,
        db=db,
    )
    return {"ok": True}


@router.post("/students/{student_profile_id}/transfer")
async def move_student(
    student_profile_id: int,
    payload: TransferInput,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await transfer_student(user, student_profile_id=student_profile_id, target_classroom_id=payload.target_classroom_id, db=db)
    return {"ok": True}


@router.post("/{target_profile_id}/block")
async def block_account(
    target_profile_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await set_account_blocked(user, target_profile_id=target_profile_id, blocked=True, db=db)
    return {"ok": True}


@router.post("/{target_profile_id}/restore")
async def restore_account(
    target_profile_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    await set_account_blocked(user, target_profile_id=target_profile_id, blocked=False, db=db)
    return {"ok": True}


@router.post("/{target_profile_id}/reset-password")
async def reset_password(
    target_profile_id: int,
    user: AuthPrincipal = Depends(require_roles("admin", "teacher")),
    db: AsyncSession = Depends(get_db),
):
    password = await reset_temporary_password(user, target_profile_id=target_profile_id, db=db)
    return {"temporary_password": password}
