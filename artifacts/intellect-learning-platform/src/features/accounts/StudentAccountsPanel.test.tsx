import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';
import { StudentAccountsPanel } from './StudentAccountsPanel';

vi.mock('@tanstack/react-query', () => ({ useQueryClient: () => ({ invalidateQueries: vi.fn() }) }));
vi.mock('@/lib/api', () => {
  const mutation = () => ({ mutateAsync: vi.fn(), isPending: false });
  return {
    useClassroomStudents: () => ({ data: [{ student_id: 1, profile_id: 12, name: 'Same Name', login: 'seventh.login', grade: 7, status: 'active', must_change_password: true, enrolled_at: '' }], isLoading: false }),
    useCreateStudent: mutation, useBulkCreateStudents: mutation, useResetAccountPassword: mutation,
    useSetAccountBlocked: mutation, useTransferStudent: mutation, useDeleteStudentAccount: mutation,
    resetClassroomPasswords: vi.fn(),
  };
});

const props = {
  classroomId: 7,
  classrooms: [{ id: 7, name: '7', grade: 7, academic_year: '2026/27', student_count: 1, teachers: [] }],
  onCredentials: vi.fn(), onError: vi.fn(),
};

describe('student removal permissions', () => {
  it('shows the removal control for the administrator and identifies the exact row by login', () => {
    const html = renderToStaticMarkup(createElement(StudentAccountsPanel, { ...props, isAdmin: true }));
    expect(html).toContain('Удалить ученика: Same Name');
    expect(html).toContain('seventh.login');
  });
  it('does not expose removal controls to a teacher', () => {
    const html = renderToStaticMarkup(createElement(StudentAccountsPanel, { ...props, isAdmin: false }));
    expect(html).not.toContain('Удалить ученика');
    expect(html).toContain('seventh.login');
  });
});
