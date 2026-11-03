import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useQuery } from '@tanstack/react-query';
import { setAuthSession } from '../authSession';
import { useStudentLearningReport, useStudentLessonReport, useStudentTutorSummary, useStudentTutorDialogue } from './dashboard';

vi.mock('@tanstack/react-query', () => ({ useQuery: vi.fn() }));
const viewer = (role: 'admin' | 'teacher', profile_id = 1) => ({
  access_token: 'test', refresh_token: 'test', expires_in: 3600,
  user: { id: profile_id, profile_id, role, grade: null, login_name: 'test', name: 'Test', must_change_password: false },
});

beforeEach(() => {
  vi.stubGlobal('localStorage', { setItem: vi.fn(), removeItem: vi.fn(), getItem: () => null });
  vi.mocked(useQuery).mockClear();
});

describe('educator report cache scope', () => {
  it('isolates learning, breakdown and tutor caches when an admin changes to another viewer', () => {
    const collect = () => {
      useStudentLearningReport(7); useStudentLessonReport(7, 9); useStudentTutorSummary(7); useStudentTutorDialogue(7, 9);
      return vi.mocked(useQuery).mock.calls.slice(-4).map(call => call[0].queryKey);
    };
    setAuthSession(viewer('admin'));
    const adminKeys = collect();
    setAuthSession(viewer('teacher', 2));
    const teacherKeys = collect();
    adminKeys.forEach((key, index) => expect(key).not.toEqual(teacherKeys[index]));
  });

  it('also changes cache scope when the role changes for the same profile', () => {
    setAuthSession(viewer('admin'));
    useStudentLearningReport(7);
    const admin = vi.mocked(useQuery).mock.calls.at(-1)?.[0].queryKey;
    setAuthSession(viewer('teacher'));
    useStudentLearningReport(7);
    expect(vi.mocked(useQuery).mock.calls.at(-1)?.[0].queryKey).not.toEqual(admin);
  });
});
