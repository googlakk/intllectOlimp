import { beforeEach, describe, expect, it, vi } from 'vitest';
import { request } from './client';
import { deleteStudentAccount, resetAccountPassword, resetClassroomPasswords, restoreStudentAccount } from './accounts';

vi.mock('./client', () => ({ request: vi.fn(), ApiError: class extends Error {} }));

describe('temporary password requests', () => {
  beforeEach(() => vi.mocked(request).mockReset());
  it('keeps legacy automatic teacher reset without a body', async () => {
    await resetAccountPassword(5);
    expect(request).toHaveBeenCalledExactlyOnceWith('/accounts/5/reset-password', { method: 'POST' });
  });
  it('sends an explicit temporary password for one student', async () => {
    await resetAccountPassword({ profileId: 12, temporary_password: '123456' });
    expect(request).toHaveBeenCalledExactlyOnceWith('/accounts/12/reset-password', { method: 'POST', body: JSON.stringify({ temporary_password: '123456' }) });
  });
  it('resets only the explicit selected students and omits the password for automatic issuance', async () => {
    await resetClassroomPasswords(7, [11, 12]);
    expect(request).toHaveBeenCalledExactlyOnceWith('/accounts/classrooms/7/reset-passwords', { method: 'POST', body: JSON.stringify({ profile_ids: [11, 12] }) });
  });
});

describe('student lifecycle requests', () => {
  beforeEach(() => vi.mocked(request).mockReset());
  it('removes only the selected profile from the expected classroom', async () => {
    await deleteStudentAccount(7, 12);
    expect(request).toHaveBeenCalledExactlyOnceWith('/accounts/classrooms/7/students/12', { method: 'DELETE' });
  });
  it('restores the exact profile to the explicitly chosen classroom', async () => {
    await restoreStudentAccount(12, 8);
    expect(request).toHaveBeenCalledExactlyOnceWith('/accounts/students/12/restore', { method: 'POST', body: JSON.stringify({ target_classroom_id: 8 }) });
  });
});
