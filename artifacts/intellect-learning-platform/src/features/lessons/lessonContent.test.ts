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
