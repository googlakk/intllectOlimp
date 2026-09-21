import { describe, expect, it } from 'vitest';

import { ktpUploadInvalidationKeys } from './uploadWorkflow';

describe('ktpUploadInvalidationKeys', () => {
  it('keeps KTP upload cache refresh targets explicit', () => {
    expect(ktpUploadInvalidationKeys()).toEqual([
      ['subjects'],
      ['sections'],
      ['topics'],
    ]);
  });
});
