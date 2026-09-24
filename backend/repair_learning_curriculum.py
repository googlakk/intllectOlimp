"""Rebuild inferred learning links after the learning-cycle migration.

Defaults to a read-only report. Run with --apply against the intended database
only after reviewing the report. Published content and completed attempts are
never regenerated or deleted.
"""
import argparse
import asyncio
from sqlalchemy import select
from database import AsyncSessionLocal, engine
from models import Subject, Topic, Section
from services.curriculum_graph import rebuild_subject_graph


async def run(apply: bool):
    async with AsyncSessionLocal() as db:
        subjects = (await db.scalars(select(Subject).order_by(Subject.id))).all()
        for subject in subjects:
            topics = (await db.scalars(select(Topic).join(Section).where(
                Section.subject_id == subject.id, Topic.archived_at.is_(None)))).all()
            print(f'{subject.id}: {subject.name}, {subject.grade} класс — {len(topics)} занятий')
            if apply:
                result = await rebuild_subject_graph(subject.id, db)
                await db.commit()
                print(f'  Обновлены связи: {result}')
    await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Сохранить новые автоматически выведенные связи')
    asyncio.run(run(parser.parse_args().apply))
