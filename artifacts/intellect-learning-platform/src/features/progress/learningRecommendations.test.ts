import { describe, expect, it } from 'vitest';
import type { CurriculumMapTopic } from '@/lib/api/types';
import { recommendLearning } from './learningRecommendations';
const topic = (id: number, fields: Partial<CurriculumMapTopic> = {}): CurriculumMapTopic => ({ id, name: `Тема ${id}`, hours: 1, section_id: 1, section_name: 'Раздел', subject_id: 1, subject_name: 'Математика', grade: 7, state: 'available', readiness_score: 1, reason: '', unlocked_by_topic_id: null, lesson_status: 'published', mastery_status: null, attempts: 0, progress_status: 'not_started', ...fields });
describe('next learning action', () => {
  it('prioritizes unfinished lesson', () => expect(recommendLearning([topic(1), topic(2, { progress_status: 'in_progress' })])?.topic.id).toBe(2));
  it('uses linked reflection after an unsuccessful completed assessment', () => expect(recommendLearning([topic(1, { progress_status: 'completed', mastery_status: 'needs_practice' }), topic(2, { lesson_type: 'reflection', source_assessment_topic_id: 1 })])?.topic.id).toBe(2));
  it('does not recommend preparing topics or completed reviews without evidence', () => expect(recommendLearning([topic(1, { lesson_status: 'preparing' }), topic(2, { progress_status: 'completed' })])).toBeNull());
  it('does not block published topics by readiness', () => expect(recommendLearning([topic(1, { state: 'locked' })])?.topic.id).toBe(1));
});
