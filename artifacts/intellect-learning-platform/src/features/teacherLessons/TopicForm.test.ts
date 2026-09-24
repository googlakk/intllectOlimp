import { describe, expect, it } from 'vitest';
import type { SectionOutline, Topic } from '@/lib/api';
import { defaultSourceAssessment } from './TopicForm';
const topic = (id: number, lesson_type: string, extra: Partial<Topic> = {}): Topic => ({ id, lesson_type, name: 'Тема', section_id: 1, ktp_number: null, hours: 1, learning_objectives: null, skills: [], resources: null, ...extra });
const section: SectionOutline = { id: 1, subject_id: 1, name: 'Раздел', sort_order: 1, total_hours: 3, topics: [topic(1, 'assessment'), topic(2, 'assessment'), topic(3, 'assessment', { archived_at: '2026-01-01' })] };
describe('reflection source defaults', () => {
  it('suggests the nearest active assessment for a new lesson', () => expect(defaultSourceAssessment(section)).toBe('2'));
  it('preserves general reflection while editing', () => expect(defaultSourceAssessment(section, topic(4, 'reflection', { source_assessment_topic_id: null }))).toBe(''));
  it('preserves a historical archived source', () => expect(defaultSourceAssessment(section, topic(4, 'reflection', { source_assessment_topic_id: 3 }))).toBe('3'));
});
