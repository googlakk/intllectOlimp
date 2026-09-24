import { describe, expect, it } from 'vitest';

import { lessonEditorInvalidationKeys } from './workflow';

describe('lessonEditorInvalidationKeys', () => {
  it('keeps editor cache invalidation targets explicit and stable', () => {
    expect(lessonEditorInvalidationKeys(42)).toEqual(expect.arrayContaining([
      ['lesson', 42],
      ['lesson-status', 42],
      ['subject-outline'],
      ['curriculum-graph'],
      ['lesson-manifest', 42],
    ]));
  });
});
