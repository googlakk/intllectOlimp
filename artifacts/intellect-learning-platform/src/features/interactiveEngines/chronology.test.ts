import { describe, expect, it } from 'vitest';
import { checkChronology, chronologyScore, clampYear, defaultTolerance, deltaLabel, initialPlacement, normalizeEvents, parseYear, type ChronologyEvent } from './chronology';

const EVENTS: ChronologyEvent[] = [
  { id: 'a', label: 'Основание Кокандского ханства', year: 1709 },
  { id: 'b', label: 'Поход на Южный Кыргызстан', year: 1762 },
  { id: 'c', label: 'Восстание против Коканда', year: 1845 },
  { id: 'd', label: 'Присоединение к России', year: 1876 },
];

describe('chronology', () => {
  it('раскладывает карточки внутри ленты и не в правильном порядке', () => {
    const placed = initialPlacement(EVENTS);
    const order = Object.entries(placed).sort((x, y) => x[1] - y[1]).map(([id]) => id);
    expect(order).not.toEqual(['a', 'b', 'c', 'd']);
    expect(initialPlacement(EVENTS)).toEqual(placed); // та же раскладка после перезагрузки
  });

  it('оценивает с допуском и объясняет ошибку', () => {
    const tolerance = defaultTolerance(EVENTS);
    expect(tolerance).toBe(8);
    const verdicts = checkChronology(EVENTS, { a: 1712, b: 1762, c: 1821, d: 1876 }, tolerance);
    expect(verdicts.map((v) => v.correct)).toEqual([true, true, false, true]);
    expect(chronologyScore(verdicts)).toBe(75);
    expect(deltaLabel(verdicts[2].delta)).toBe('на 24 года раньше');
    expect(deltaLabel(1)).toBe('на 1 год позже');
    expect(deltaLabel(-11)).toBe('на 11 лет раньше');
  });
});

describe('normalizeEvents', () => {
  it('чинит годы строкой, пустые и повторяющиеся id, отбрасывает мусор', () => {
    const events = normalizeEvents([
      { id: 'a', label: 'Основание', year: '1709' },
      { id: 'a', label: 'Поход', year: '1762 г.' },
      { label: 'Без id', year: 1845 },
      { id: 'x', label: '', year: 1900 },
      { id: 'y', label: 'Без года', year: 'давно' },
      null,
    ]);
    expect(events.map((event) => [event.id, event.year])).toEqual([['a', 1709], ['a-2', 1762], ['event-3', 1845]]);
    expect(normalizeEvents('не массив')).toEqual([]);
  });

  it('понимает годы до нашей эры и держит год в границах ленты', () => {
    expect(parseYear('500 г. до н. э.')).toBe(-500);
    expect(parseYear(-44)).toBe(-44);
    expect(clampYear(0, { from: 1690, to: 1890 })).toBe(1690);
  });
});
