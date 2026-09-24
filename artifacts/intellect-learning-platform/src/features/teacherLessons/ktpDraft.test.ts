import { describe, expect, it } from 'vitest';
import type { KtpDraft } from '@/lib/api';
import { normalizeKtpDraft, summarizeKtpDraft, validateKtpDraft } from './ktpDraft';

const draft: KtpDraft = {
  subject_name: ' Математика ', grade: 7, hours_per_week: 4, hours_per_year: 99,
  instruction_language: 'ru',
  sections: [{ name: ' Числа ', total_hours: 99, topics: [
    { ktp_number: '1', name: ' Целые числа ', hours: 2, lesson_type: 'study', learning_objectives: ' Сравнивать ', skills: [], resources: '' },
    { ktp_number: '2', name: 'Практика', hours: 1, lesson_type: 'study', learning_objectives: '', skills: [], resources: '' },
  ] }],
};

describe('KTP draft helpers', () => {
  it('summarizes sections, topics, hours and missing objectives', () => {
    expect(summarizeKtpDraft(draft)).toEqual({ sections: 1, topics: 2, hours: 3, topicsWithoutObjectives: 1 });
  });

  it('normalizes editable draft and recalculates hours', () => {
    const normalized = normalizeKtpDraft(draft);
    expect(normalized.subject_name).toBe('Математика');
    expect(normalized.sections[0].name).toBe('Числа');
    expect(normalized.hours_per_year).toBe(3);
  });

  it('limits the standard 2026 workflow to grades 7-10', () => {
    expect(validateKtpDraft({ ...draft, grade: 6 })).toContain('7–10');
    expect(validateKtpDraft(draft)).toBeNull();
  });
});
