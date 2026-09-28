import { describe, expect, it } from 'vitest';
import type { SectionOutline, Topic } from '@/lib/api/types';
import { catalogLessonChoices, componentLessonPath } from './lessonPicker';

const topic: Topic = { id: 21, section_id: 1, ktp_number: '3', name: 'Линейные функции', hours: 1, lesson_type: 'study', learning_objectives: null, skills: [], resources: null, lesson_id: 50, lesson_status: 'draft' };
const sections: SectionOutline[] = [{ id: 1, subject_id: 2, name: 'Алгебра', sort_order: 1, total_hours: 3, topics: [topic, { ...topic, id: 22, lesson_id: null }, { ...topic, id: 23, archived_at: '2026-09-29' }] }];

describe('catalog lesson picker', () => {
  it('offers existing nonarchived lessons using topic identity', () => {
    expect(catalogLessonChoices(sections, '').map(({ topic: item }) => item.id)).toEqual([21]);
    expect(catalogLessonChoices(undefined, '')).toEqual([]);
  });
  it('searches topic title, section and KTP number', () => {
    expect(catalogLessonChoices(sections, ' ФУНКЦИИ ')).toHaveLength(1);
    expect(catalogLessonChoices(sections, 'алгебра')).toHaveLength(1);
    expect(catalogLessonChoices(sections, '3')).toHaveLength(1);
    expect(catalogLessonChoices(sections, 'история')).toHaveLength(0);
  });
  it('routes to topic editor and preserves component as encoded query value', () => {
    expect(componentLessonPath(21, 'rule-discovery')).toBe('/dashboard/lessons/21?add_component=rule-discovery');
    expect(componentLessonPath(21, 'x&next=/other')).toBe('/dashboard/lessons/21?add_component=x%26next%3D%2Fother');
  });
});
