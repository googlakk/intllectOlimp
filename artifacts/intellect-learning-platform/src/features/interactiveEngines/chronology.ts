/** «Лента событий»: чистая логика — раскладка карточек, оценка, разбор. */

export type ChronologyEvent = { id: string; label: string; year: number; explanation?: string; lane?: string };

export type ChronologyVerdict = {
  id: string;
  label: string;
  year: number;
  placed: number;
  delta: number;       // placed − year: минус — раньше, плюс — позже
  correct: boolean;
  explanation?: string;
};

/**
 * Данные от модели бывают неаккуратными: год строкой («1916», «500 до н. э.»),
 * пустые или повторяющиеся id. Приводим к рабочему виду, а не теряем событие.
 */
export function normalizeEvents(raw: unknown): ChronologyEvent[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const events: ChronologyEvent[] = [];
  raw.forEach((item, index) => {
    if (!item || typeof item !== 'object') return;
    const event = item as Record<string, unknown>;
    const year = parseYear(event.year);
    const label = String(event.label ?? '').trim();
    if (year === null || !label) return;
    let id = String(event.id ?? '').trim() || `event-${index + 1}`;
    while (seen.has(id)) id = `${id}-${index + 1}`;
    seen.add(id);
    events.push({
      id, label, year,
      ...(typeof event.explanation === 'string' ? { explanation: event.explanation } : {}),
      ...(typeof event.lane === 'string' ? { lane: event.lane } : {}),
    });
  });
  return events;
}

export function parseYear(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? Math.round(value) : null;
  if (typeof value !== 'string') return null;
  const match = value.match(/-?\d{1,4}/);
  if (!match) return null;
  const year = Number(match[0]);
  // «до н. э.» / «до нашей эры» / «б.з.ч.» — год до нашей эры.
  return /до\s*н\.?\s*э|до\s+нашей\s+эры|б\.?\s*з\.?\s*ч/i.test(value) ? -Math.abs(year) : year;
}

export function clampYear(year: number, range: { from: number; to: number }): number {
  return Math.min(range.to, Math.max(range.from, Math.round(year)));
}

/** Допуск по умолчанию — около 5% охвата ленты, не меньше года. */
export function defaultTolerance(events: ChronologyEvent[]): number {
  if (!events.length) return 1;
  const years = events.map((event) => event.year);
  return Math.max(1, Math.round((Math.max(...years) - Math.min(...years)) / 20));
}

/** Границы ленты с полями, чтобы крайние события не прижимались к краю. */
export function chronologyRange(events: ChronologyEvent[]): { from: number; to: number } {
  const years = events.map((event) => event.year);
  const min = Math.min(...years);
  const max = Math.max(...years);
  const pad = Math.max(2, Math.round((max - min) * 0.12));
  return { from: min - pad, to: max + pad };
}

/**
 * Начальная раскладка: карточки равномерно по ленте, но в перемешанном порядке —
 * так раскладка не подсказывает ответ. Перемешивание детерминированное (по id),
 * чтобы после перезагрузки ученик видел ту же картину.
 */
export function initialPlacement(events: ChronologyEvent[]): Record<string, number> {
  const { from, to } = chronologyRange(events);
  const order = [...events].sort((a, b) => hash(a.id + a.label) - hash(b.id + b.label));
  // Если перемешивание случайно совпало с правильным порядком — сдвигаем на одну позицию.
  const sortedIds = [...events].sort((a, b) => a.year - b.year).map((event) => event.id);
  if (order.length > 1 && order.every((event, index) => event.id === sortedIds[index])) order.push(order.shift()!);
  const step = (to - from) / (order.length + 1);
  return Object.fromEntries(order.map((event, index) => [event.id, Math.round(from + step * (index + 1))]));
}

function hash(text: string): number {
  let value = 2166136261;
  for (let index = 0; index < text.length; index += 1) value = Math.imul(value ^ text.charCodeAt(index), 16777619);
  return value >>> 0;
}

export function checkChronology(events: ChronologyEvent[], placed: Record<string, number>, tolerance: number): ChronologyVerdict[] {
  return events.map((event) => {
    const position = placed[event.id] ?? Number.NaN;
    const delta = position - event.year;
    return {
      id: event.id, label: event.label, year: event.year, placed: position, delta,
      correct: Number.isFinite(delta) && Math.abs(delta) <= tolerance, explanation: event.explanation,
    };
  });
}

/** Доля верно поставленных событий, 0–100; блок засчитан от 80. */
export function chronologyScore(verdicts: ChronologyVerdict[]): number {
  return verdicts.length ? Math.round((verdicts.filter((verdict) => verdict.correct).length / verdicts.length) * 100) : 0;
}

export function yearLabel(year: number): string {
  return year < 0 ? `${-year} г. до н. э.` : `${year} г.`;
}

/** «на 12 лет раньше» / «на 1 год позже». */
export function deltaLabel(delta: number): string {
  const size = Math.abs(delta);
  const word = size % 10 === 1 && size % 100 !== 11 ? 'год'
    : [2, 3, 4].includes(size % 10) && ![12, 13, 14].includes(size % 100) ? 'года' : 'лет';
  return `на ${size} ${word} ${delta < 0 ? 'раньше' : 'позже'}`;
}
