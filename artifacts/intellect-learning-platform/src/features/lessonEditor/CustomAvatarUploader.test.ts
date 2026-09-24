import { describe, expect, it } from 'vitest';
import { customAvatarFileError } from './CustomAvatarUploader';

describe('customAvatarFileError', () => {
  it('accepts PNG and JPEG files up to 10 MB', () => {
    expect(customAvatarFileError('image/png', 1024)).toBe('');
    expect(customAvatarFileError('image/jpeg', 10 * 1024 * 1024)).toBe('');
  });

  it('rejects unsupported and oversized files', () => {
    expect(customAvatarFileError('image/webp', 1024)).toContain('PNG');
    expect(customAvatarFileError('image/png', 10 * 1024 * 1024 + 1)).toContain('10 МБ');
  });
});
