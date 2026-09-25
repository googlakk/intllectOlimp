import { describe, expect, it } from 'vitest';
import { linkSummary, topicLinkState } from './linkState';

const link = (status: 'confirmed' | 'suggested') => ({ section_id: 1, status, source: 'match' as const, role: 'primary' as const, score: 0.5, number: '§ 1', title: 'А' });
const topic = (links: ReturnType<typeof link>[], lesson_type = 'study') =>
  ({ id: 1, ktp_number: '1', name: 'Тема', lesson_type, uses_covered_topics: lesson_type === 'review', rejected: false, links });

describe('topicLinkState', () => {
  it('различает подтверждённые, предложенные, повторение и ненайденные темы', () => {
    expect(topicLinkState(topic([link('suggested'), link('confirmed')]))).toBe('confirmed');
    expect(topicLinkState(topic([link('suggested')]))).toBe('suggested');
    expect(topicLinkState(topic([], 'review'))).toBe('covered');
    expect(topicLinkState(topic([]))).toBe('none');
    expect(topicLinkState({ ...topic([]), rejected: true })).toBe('rejected');
    expect(linkSummary([topic([]), topic([link('suggested')])])).toEqual({ confirmed: 0, suggested: 1, covered: 0, rejected: 0, none: 1 });
  });
});
