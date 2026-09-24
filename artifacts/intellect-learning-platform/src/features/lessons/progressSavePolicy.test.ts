import { describe, expect, it } from 'vitest';

import type { SaveProgressInput } from '@/lib/api';
import { coalesceProgressSave, shouldSaveProgressImmediately } from './progressSavePolicy';

const input = (step: number): SaveProgressInput => ({
  student_id: 7,
  topic_id: 2,
  status: 'in_progress',
  current_step: step,
  max_opened_step: step,
});

describe('progress save policy', () => {
  it('flushes completion immediately and debounces in-progress updates', () => {
    expect(shouldSaveProgressImmediately('completed')).toBe(true);
    expect(shouldSaveProgressImmediately('in_progress')).toBe(false);
  });

  it('keeps the newest in-progress payload when saves are coalesced', () => {
    expect(coalesceProgressSave(input(1), input(2))).toMatchObject({
      current_step: 2,
      max_opened_step: 2,
    });
  });
});
