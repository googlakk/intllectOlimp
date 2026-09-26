import { describe, expect, it } from 'vitest';
import { causeScore, checkFactors, diagramLayout, normalizeFactors } from './causeEffect';

const RAW = [
  { id: 'tax', label: 'Тяжёлые налоги Коканда', role: 'cause', kind: 'economic' },
  { id: 'raid', label: 'Карательный поход на кочевья', role: 'trigger', kind: 'political' },
  { id: 'war', label: 'Восстание 1845 года', role: 'consequence', term: 'short' },
  { id: 'tea', label: 'Мода на чай в Европе', role: 'unrelated' },
];

describe('causeEffect', () => {
  it('нормализует данные модели и отбрасывает неизвестные роли', () => {
    const factors = normalizeFactors([...RAW, { id: 'x', label: 'Странное', role: 'reason' }, { label: 'Без id', role: 'cause' }]);
    expect(factors.map((factor) => factor.id)).toEqual(['tax', 'raid', 'war', 'tea', 'factor-6']);
    expect(normalizeFactors(null)).toEqual([]);
    expect(normalizeFactors([{ id: 'a', label: 'X', role: ' Cause ' }, { id: 'b', label: 'Y', role: 'повод' }, { id: 'c', label: 'Z', role: 'Себеп' }])
      .map((factor) => factor.role)).toEqual(['cause', 'trigger', 'cause']);
  });

  it('оценивает роли: путаница причины и повода — ошибка', () => {
    const verdicts = checkFactors(normalizeFactors(RAW), { tax: 'cause', raid: 'cause', war: 'consequence', tea: 'unrelated' });
    expect(verdicts.map((verdict) => verdict.correct)).toEqual([true, false, true, true]);
    expect(causeScore(verdicts)).toBe(75);
  });

  it('раскладывает схему: причины слева, последствия справа, на телефоне — столбиком', () => {
    const chosen = { tax: 'cause', raid: 'trigger', war: 'consequence' } as const;
    const wide = diagramLayout(chosen, ['tax', 'raid', 'war', 'tea'], 900);
    expect(wide.positions.tax.x).toBeLessThan(wide.positions.event.x);
    expect(wide.positions.war.x).toBeGreaterThan(wide.positions.event.x);
    expect(wide.positions.tea).toBeUndefined();
    const narrow = diagramLayout(chosen, ['tax', 'raid', 'war'], 360);
    expect(narrow.positions.war.y).toBeGreaterThan(narrow.positions.event.y);
  });
});
