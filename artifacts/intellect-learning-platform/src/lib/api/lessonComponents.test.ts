import { beforeEach, describe, expect, it, vi } from 'vitest';
import { request } from './client';
import { getLessonComponentContext, insertLessonComponent, prepareLessonComponent } from './lessonComponents';

vi.mock('./client', () => ({ request: vi.fn() }));

describe('textbook component API', () => {
  beforeEach(() => { vi.mocked(request).mockReset(); });

  it('loads context without starting generation', async () => {
    vi.mocked(request).mockResolvedValue({ revision: 'v1', objectives: [], sources: [] });
    await getLessonComponentContext(42);
    expect(request).toHaveBeenCalledExactlyOnceWith('/lessons/42/components/context');
  });

  it('sends the selected source, goal and insertion position for preparation', async () => {
    const input = { component: 'RuleDiscovery', objective_id: 'goal1', after_index: -1,
      base_revision: 'v1', source_section_id: 12, source_item_id: 23 };
    await prepareLessonComponent(42, input);
    expect(request).toHaveBeenCalledExactlyOnceWith('/lessons/42/components/prepare', {
      method: 'POST', body: JSON.stringify(input),
    });
  });

  it('keeps the same insertion identity on a retry without calling preparation', async () => {
    const input = { block: { component: 'RuleDiscovery', content: {} }, after_index: 0,
      base_revision: 'v1', context_fingerprint: 'signed-preview', request_id: 'stable-request-id' };
    vi.mocked(request).mockRejectedValueOnce(new Error('Temporary failure')).mockResolvedValueOnce({ id: 42 });
    await expect(insertLessonComponent(42, input)).rejects.toThrow('Temporary failure');
    await insertLessonComponent(42, input);
    expect(request).toHaveBeenCalledTimes(2);
    expect(vi.mocked(request).mock.calls[0]).toEqual(vi.mocked(request).mock.calls[1]);
    expect(vi.mocked(request).mock.calls[1][0]).toBe('/lessons/42/components/insert');
  });

  it('surfaces stale preview errors instead of silently regenerating', async () => {
    vi.mocked(request).mockRejectedValue(new Error('Урок изменился'));
    await expect(insertLessonComponent(42, { block: { component: 'RuleDiscovery', content: {} },
      after_index: null, base_revision: 'old', context_fingerprint: 'signed', request_id: 'id' })).rejects.toThrow('Урок изменился');
    expect(request).toHaveBeenCalledTimes(1);
  });
});
