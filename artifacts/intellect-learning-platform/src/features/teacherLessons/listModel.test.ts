import { describe, expect, it } from 'vitest';
import { lessonStatusView, lessonTypeLabel, parseKtpJsonText } from './listModel';

describe('teacher lesson list model', () => {
  it('formats known and unknown lesson types', () => {
    expect(lessonTypeLabel('study')).toBe('изучение нового');
    expect(lessonTypeLabel('assessment')).toBe('контроль');
    expect(lessonTypeLabel('seminar')).toBe('seminar');
  });

  it('hides status badge while lesson status is loading', () => {
    expect(lessonStatusView(undefined, true)).toBeNull();
  });

  it('maps missing, draft and published lesson status to badge view data', () => {
    expect(lessonStatusView(null, false)).toEqual({
      badgeClasses: 'bg-muted text-muted-foreground',
      badgeText: 'Нет урока',
    });
    expect(lessonStatusView({ lesson_status: 'draft' }, false)).toEqual({
      badgeClasses: 'bg-yellow-500/10 text-yellow-600',
      badgeText: 'Черновик',
    });
    expect(lessonStatusView({ lesson_status: 'published' }, false)).toEqual({
      badgeClasses: 'bg-green-500/10 text-green-600',
      badgeText: 'Опубликован',
    });
  });

  it('parses KTP JSON text and reports invalid JSON in user-facing wording', () => {
    expect(parseKtpJsonText('{"subject":"math"}')).toEqual({ subject: 'math' });
    expect(() => parseKtpJsonText('{bad json')).toThrow('Файл должен быть валидным JSON');
  });
});
