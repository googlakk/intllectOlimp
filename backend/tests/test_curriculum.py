from datetime import date

import pytest
from sqlalchemy import select

from curriculum import drive_file_id, lesson_parts, merge_key, quarter_for
from models import GeneratedLesson, Progress, SchoolClass, Section, Student, Subject, Topic
from objectives import quality_report
from tests.factories import login, make_user


# ---- pure rules -------------------------------------------------------------

def test_quarter_split_matches_school_weeks():
    total = 136  # 4 h/week, Математика 7Б
    hours_by_quarter = {1: 0, 2: 0, 3: 0, 4: 0}
    for position in range(0, total, 4):
        hours_by_quarter[quarter_for(position, total)] += 4
    assert hours_by_quarter == {1: 32, 2: 28, 3: 32, 4: 44}


@pytest.mark.parametrize("name", ["Контрольная работа", "Закрепление 2 главы", "Повторение", "Ключевые идеи 3 главы", "Итоговая контрольная работа"])
def test_generic_rows_never_merge(name):
    assert merge_key(name) is None


def test_same_topic_rows_merge_case_insensitive():
    assert merge_key("Площадь поверхности куба и кубоида") == merge_key("площадь  поверхности куба и кубоида.")


def test_parts_grow_with_hours():
    assert [len(lesson_parts(h)) for h in (1, 2, 3, 4, 6)] == [1, 2, 3, 4, 4]


def test_drive_links():
    file_id = "1AbCdEfGhIjKlMnOpQrStUv"
    assert drive_file_id(f"https://drive.google.com/file/d/{file_id}/view?usp=sharing") == file_id
    assert drive_file_id(f"https://drive.google.com/open?id={file_id}") == file_id
    assert drive_file_id("https://youtube.com/watch?v=x") is None


OBJECTIVES = "Ученик умеет складывать дроби"


def _lesson(extra=()):
    oid = quality_report([], OBJECTIVES)["objectives"][0]["id"]
    return oid, [
        *extra,
        {"component": "RetrievalCheck", "content": {"question": "?", "type": "multiple_choice", "options": ["1", "2", "3", "4"], "correct_answer": "1", "explanation": ".", "objective_ids": [oid], "evidence_stage": "diagnostic"}},
        {"component": "ShortExplanation", "content": {"title": "t", "text": "x", "key_concepts": [], "objective_ids": [oid], "evidence_stage": "explanation"}},
        {"component": "GuidedPractice", "content": {"question": "q", "hints": [], "input_type": "text", "correct_answer": "a", "explanation": ".", "objective_ids": [oid], "evidence_stage": "practice"}},
        {"component": "MasteryCheck", "content": {"questions": [{"question": "q", "type": "numeric", "correct_answer": "1", "explanation": ".", "dimension": oid, "objective_ids": [oid]}], "evidence_stage": "assessment"}},
    ]


def test_review_warmup_about_previous_topic_does_not_break_quality():
    review = {"component": "RetrievalCheck", "content": {"question": "Прошлая тема?", "type": "multiple_choice", "options": ["a", "b", "c", "d"], "correct_answer": "a", "explanation": ".", "evidence_stage": "review"}}
    _, blocks = _lesson([review])
    result = quality_report(blocks, OBJECTIVES)
    assert result["quality_report"]["publishable"], result["quality_report"]["errors"]
    warmup = result["normalized_blocks"][0]["content"]
    # Normalisation must not relabel the warm-up as a diagnostic of the current topic.
    assert warmup["evidence_stage"] == "review" and "objective_ids" not in warmup


def test_video_block_requires_drive_link():
    good = {"component": "VideoLesson", "content": {"title": "v", "drive_url": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/view"}}
    bad = {"component": "VideoLesson", "content": {"title": "v", "drive_url": "https://example.com/v.mp4"}}
    _, ok_blocks = _lesson([good])
    _, bad_blocks = _lesson([bad])
    assert quality_report(ok_blocks, OBJECTIVES)["quality_report"]["publishable"]
    codes = [e["code"] for e in quality_report(bad_blocks, OBJECTIVES)["quality_report"]["errors"]]
    assert "invalid_video_link" in codes


# ---- API --------------------------------------------------------------------

async def _course(db):
    subject = Subject(name="Математика", grade=7, hours_per_week=4, hours_per_year=136)
    db.add(subject)
    await db.flush()
    section = Section(subject_id=subject.id, name="Глава 10", sort_order=1, total_hours=10)
    db.add(section)
    await db.flush()
    first = Topic(section_id=section.id, name="Площадь поверхности", hours=2, quarter=4, sort_number=2, learning_objectives=OBJECTIVES, skills=[])
    earlier = Topic(section_id=section.id, name="Объём куба", hours=2, quarter=4, sort_number=1, skills=[])
    db.add_all([first, earlier])
    await db.flush()
    repeat = Topic(section_id=section.id, name="Площадь поверхности", hours=2, quarter=4, sort_number=3, lesson_topic_id=first.id, skills=[])
    db.add(repeat)
    await db.commit()
    return subject, first, repeat, earlier


def _parted_blocks():
    oid, blocks = _lesson()
    for block in blocks[:2]:
        block["content"]["lesson_part"] = 1
    for block in blocks[2:]:
        block["content"]["lesson_part"] = 2
    return blocks


async def test_topics_ordered_by_quarter_and_number(client, db):
    subject, *_ = await _course(db)
    teacher = await make_user(db, "teacher", "Учитель Один")
    await login(client, teacher)
    names = [t["sort_number"] for t in (await client.get(f"/api/subjects/{subject.id}/topics")).json()]
    assert names == [1, 2, 3]


async def test_quarter_plan_lists_only_lesson_owning_rows(client, db):
    subject, first, repeat, earlier = await _course(db)
    db.add(GeneratedLesson(topic_id=earlier.id, blocks=[], lesson_metadata={}, status="published"))
    await db.commit()
    teacher = await make_user(db, "teacher", "Учитель Один")
    await login(client, teacher)
    plan = (await client.get(f"/api/lessons/quarter-plan?subject_id={subject.id}&quarter=4")).json()
    assert [(p["topic_id"], p["lesson_status"]) for p in plan] == [(earlier.id, "published"), (first.id, None)]


async def test_batch_generation_never_overwrites_existing_lesson(client, db):
    _, first, repeat, _ = await _course(db)
    db.add(GeneratedLesson(topic_id=first.id, blocks=[{"component": "x", "content": {}}], lesson_metadata={"keep": 1}, status="published"))
    await db.commit()
    teacher = await make_user(db, "teacher", "Учитель Один")
    await login(client, teacher)
    # Via the repeated row too: it resolves to the same owning topic.
    for topic_id in (first.id, repeat.id):
        response = await client.post("/api/lessons/generate", json={"topic_id": topic_id, "skip_existing": True})
        assert response.status_code == 409
    lesson = await db.scalar(select(GeneratedLesson).where(GeneratedLesson.topic_id == first.id))
    await db.refresh(lesson)
    assert lesson.status == "published" and lesson.lesson_metadata == {"keep": 1}


async def test_parts_open_by_delivered_mark(client, db):
    _, first, repeat, _ = await _course(db)
    school_class = SchoolClass(school_system=11, grade=7, letter="Б", program="national")
    db.add(school_class)
    db.add(GeneratedLesson(topic_id=first.id, blocks=_parted_blocks(), lesson_metadata={}, status="published"))
    await db.commit()
    student_user = await make_user(db, "student", "Ученик Один")
    student = await db.scalar(select(Student).where(Student.user_id == student_user.id))
    student.class_id = school_class.id
    await db.commit()
    teacher = await make_user(db, "teacher", "Учитель Один")

    await login(client, student_user)
    lesson = (await client.get(f"/api/lessons/{repeat.id}")).json()
    assert (lesson["total_parts"], lesson["unlocked_parts"], len(lesson["blocks"])) == (2, 1, 2)

    await login(client, teacher)
    marked = await client.post(f"/api/topics/{first.id}/deliveries", json={"class_id": school_class.id, "conducted_on": str(date(2027, 4, 1))})
    assert marked.status_code == 200
    await client.post(f"/api/topics/{repeat.id}/deliveries", json={"class_id": school_class.id, "conducted_on": str(date(2027, 4, 3))})

    await login(client, student_user)
    lesson = (await client.get(f"/api/lessons/{first.id}")).json()
    assert (lesson["unlocked_parts"], len(lesson["blocks"])) == (2, 4)


async def test_progress_on_repeated_row_is_stored_on_owning_topic(client, db):
    _, first, repeat, _ = await _course(db)
    db.add(GeneratedLesson(topic_id=first.id, blocks=_parted_blocks(), lesson_metadata={}, status="published"))
    await db.commit()
    student_user = await make_user(db, "student", "Ученик Один")
    await login(client, student_user)
    response = await client.post("/api/progress", json={"topic_id": repeat.id, "status": "in_progress", "current_step": 0, "max_opened_step": 0})
    assert response.status_code == 200, response.text
    rows = (await db.scalars(select(Progress.topic_id))).all()
    assert rows == [first.id]


async def test_admin_manages_classes_and_students(client, db):
    admin = await make_user(db, "admin", "Админ Школы")
    student_user = await make_user(db, "student", "Ученик Два")
    student = await db.scalar(select(Student).where(Student.user_id == student_user.id))
    await login(client, admin)

    created = await client.post("/api/classes", json={"school_system": 11, "grade": 8, "letter": "а", "program": "cambridge"})
    assert created.status_code == 200 and created.json()["name"] == "8А"
    duplicate = await client.post("/api/classes", json={"school_system": 11, "grade": 8, "letter": "А", "program": "cambridge"})
    assert duplicate.status_code == 409
    class_id = created.json()["id"]

    assert (await client.put(f"/api/students/{student.id}/class", json={"class_id": class_id})).json()["grade"] == 8
    listed = (await client.get("/api/classes")).json()
    assert listed[0]["student_count"] == 1

    # Deleting a class keeps the student, only unlinks them.
    assert (await client.delete(f"/api/classes/{class_id}")).status_code == 200
    students = (await client.get("/api/students")).json()
    assert students == [{"id": student.id, "name": "Ученик Два", "grade": 8, "class_id": None, "source": "local"}]


async def test_teacher_cannot_create_classes(client, db):
    teacher = await make_user(db, "teacher", "Учитель Два")
    await login(client, teacher)
    response = await client.post("/api/classes", json={"school_system": 11, "grade": 8, "letter": "Б", "program": "national"})
    assert response.status_code == 403


async def test_subject_deliveries_listed_and_removable(client, db):
    subject, first, repeat, _ = await _course(db)
    school_class = SchoolClass(school_system=11, grade=7, letter="Б", program="national")
    db.add(school_class)
    await db.commit()
    teacher = await make_user(db, "teacher", "Учитель Один")
    await login(client, teacher)
    mark = (await client.post(f"/api/topics/{repeat.id}/deliveries", json={"class_id": school_class.id, "conducted_on": "2027-04-03"})).json()
    again = await client.post(f"/api/topics/{repeat.id}/deliveries", json={"class_id": school_class.id, "conducted_on": "2027-04-03"})
    assert again.status_code == 409
    listed = (await client.get(f"/api/subjects/{subject.id}/deliveries")).json()
    assert [(d["topic_id"], d["conducted_on"]) for d in listed] == [(repeat.id, "2027-04-03")]
    assert (await client.delete(f"/api/deliveries/{mark['id']}")).status_code == 200
    assert (await client.get(f"/api/subjects/{subject.id}/deliveries")).json() == []
