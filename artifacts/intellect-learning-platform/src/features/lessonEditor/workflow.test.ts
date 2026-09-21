import { describe, expect, it } from 'vitest';

import { lessonEditorInvalidationKeys } from './workflow';

describe('lessonEditorInvalidationKeys', () => {
  it('keeps editor cache invalidation targets explicit and stable', () => {
    expect(lessonEditorInvalidationKeys(42)).toEqual([
      ['lesson', 42, 'teacher'],
      ['lesson-status', 42],
    ]);
  });
});
