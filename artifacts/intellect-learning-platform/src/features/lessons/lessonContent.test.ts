import { describe, expect, it } from 'vitest';
import { narrationSegments, narrationSpeechText, normalizeLessonMarkup } from './lessonContent';

describe('lesson content normalization', () => {
  it('repairs markdown and common undelimited root notation', () => {
    expect(normalizeLessonMarkup('**Важно:** sqrt(49) и \\sqrt{81}')).toBe(
      '**Важно:** $\\sqrt{49}$ и $\\sqrt{81}$',
    );
  });

  it('preserves already delimited formulas and code', () => {
    expect(normalizeLessonMarkup('`sqrt(4)` и $\\sqrt{9}$')).toBe('`sqrt(4)` и $\\sqrt{9}$');
  });

  it('turns markup and formulas into natural speech', () => {
    expect(narrationSpeechText('**Найдём:** $\\sqrt{49} = 7$, а $2^3 = 8$.')).toBe(
      'Найдём: квадратный корень из 49 равно 7, а 2 в кубе равно 8.',
    );
  });

  it('splits long narration without losing its ending', () => {
    const segments = narrationSegments('Первое длинное объяснение. Второе объяснение. Третий вывод.', 30);
    expect(segments.length).toBeGreaterThan(1);
    expect(segments.join(' ')).toContain('Третий вывод.');
  });

  it('also splits a long sentence without punctuation', () => {
    const source = Array.from({ length: 80 }, (_, index) => `слово${index}`).join(' ');
    const segments = narrationSegments(source, 70);
    expect(Math.max(...segments.map((segment) => segment.length))).toBeLessThanOrEqual(70);
    expect(segments.join(' ')).toBe(source);
  });
});

describe('LaTeX commands that start with \\n', () => {
  it('keeps \\neq and friends inside formulas', async () => {
    const { normalizeLessonMarkup } = await import('./lessonContent');
    expect(normalizeLessonMarkup('Смысл при $x \\neq 0$ и $x \\ne 5$')).toBe('Смысл при $x \\neq 0$ и $x \\ne 5$');
    expect(normalizeLessonMarkup('$\\neg p$, $\\nabla f$, $a \\notin B$, $\\nu$')).toBe('$\\neg p$, $\\nabla f$, $a \\notin B$, $\\nu$');
  });

  it('still turns a literal \\n into a new line', async () => {
    const { normalizeLessonMarkup } = await import('./lessonContent');
    expect(normalizeLessonMarkup('Шаг 1.\\nВычислим')).toBe('Шаг 1.\nВычислим');
    expect(normalizeLessonMarkup('Ответ:\\n2x')).toBe('Ответ:\n2x');
  });
});
