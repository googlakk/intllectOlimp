import { sameForm, sameMath } from './mathExpression';
export type BlockResult = 'idle' | 'correct' | 'incorrect' | 'partial';

export function normalizeText(value: unknown): string {
  return String(value ?? '').trim().toLocaleLowerCase();
}

export function sameSet(left: string[], right: string[]): boolean {
  const a = left.map(normalizeText).sort();
  const b = right.map(normalizeText).sort();
  return a.length === b.length && a.every((item, index) => item === b[index]);
}

export function scoreRatio(correct: number, total: number): number {
  if (total <= 0) return 0;
  return Math.round((correct / total) * 100);
}

export function resultFromScore(score: number): BlockResult {
  if (score >= 80) return 'correct';
  if (score > 0) return 'partial';
  return 'incorrect';
}

export function resultClasses(result: BlockResult): string {
  if (result === 'correct') return 'border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-300';
  if (result === 'partial') return 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300';
  if (result === 'incorrect') return 'border-destructive/30 bg-destructive/10 text-destructive';
  return 'border-border bg-muted/20 text-muted-foreground';
}

export type LinkScore = { correct: number; wrong: number; missing: number; score: number };

/** Лишние связи вычитаются: «соединить всё со всем» не должно давать 100%. */
export function scoreLinks(actual: string[], expected: string[]): LinkScore {
  const want = new Set(expected);
  const have = new Set(actual);
  const correct = [...have].filter((key) => want.has(key)).length;
  const wrong = have.size - correct;
  return { correct, wrong, missing: want.size - correct, score: scoreRatio(Math.max(0, correct - wrong), want.size) };
}

/**
 * Проверка ответа ученика. Для числовых вопросов ответ сравнивается как число:
 * «8,9», «8.90» и «8.9 г/см³» равны «8.9». Допуск по умолчанию — половина
 * последнего записанного разряда правильного ответа («8.9» → ±0,05,
 * «1917» → только 1917). Если число верное, а единица другая — `wrong_unit`.
 * Остальные ответы (текст, выражения, варианты) сравниваются как текст.
 * Те же правила на сервере: backend/services/assessment.py; общие случаи —
 * backend/fixtures/answer_check_cases.json.
 */
export type AnswerCheck = 'correct' | 'wrong_unit' | 'incorrect';

export type AnswerSpec = {
  correct: string | string[] | number;
  /** Числовой вопрос: только тогда ответ сравнивается как число с единицей. */
  numeric?: boolean;
  unit?: string;
  acceptedUnits?: string[];
  /** Явный относительный допуск (0…0,5). Без него — точность правильного ответа. */
  tolerance?: number | string;
  /**
   * choice — вариант ответа, только точно; form (выражения по умолчанию) — та же запись;
   * equivalent (числовые по умолчанию, уравнения) — по смыслу: 2√3 = √12, 1/2 = 0,5.
   */
  mode?: 'choice' | 'form' | 'equivalent';
};

type Quantity = { value: number; unit: string; decimals: number };

const NUMBER_PREFIX = /^[+-]?(?:\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,]\d+)?(?:e[+-]?\d+)?/i;
const SUPERSCRIPTS: Record<string, string> = { '²': '2', '³': '3', '¹': '1', '⁻': '-' };
const NOT_A_NUMBER = /^[+-]?(nan|inf|infinity)$/i;
/** Степень десяти после числа: «·10^-3», «×10⁻³», «* 10^5», «x10^2» — часть числа, а не единица. */
const POWER_OF_TEN = /^\s*[·*×⋅xх]\s*10\s*(?:\^\s*\(?\s*([+-]?\d+)\s*\)?|([⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+))/;
const SUPERSCRIPT_DIGITS: Record<string, string> = { '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁻': '-', '⁺': '+' };
/** Хвост после числа похож на единицу, а не на продолжение выражения («1/2», «2x+1», «= 5»). */
const NOT_A_UNIT = /[=+]|^\/\d|^[xyz]$/;
const LATIN_UNITS: Record<string, string> = {
  kg: 'кг', g: 'г', mg: 'мг', t: 'т', m: 'м', km: 'км', cm: 'см', mm: 'мм', s: 'с', h: 'ч', min: 'мин',
  N: 'Н', kN: 'кН', Pa: 'Па', kPa: 'кПа', MPa: 'МПа', J: 'Дж', kJ: 'кДж', W: 'Вт', kW: 'кВт',
  V: 'В', A: 'А', Ohm: 'Ом', 'Ω': 'Ом', l: 'л', L: 'л', Hz: 'Гц',
};

function asText(value: unknown): string {
  return value === null || value === undefined ? '' : String(value);
}

export function normalizeUnit(unit: unknown): string {
  return asText(unit)
    .replace(/[²³¹⁻]/g, (char) => SUPERSCRIPTS[char])
    .replace(/\^/g, '')
    .replace(/[\s.]+/g, '')
    .replace(/[*×⋅·]/g, '');
}

/** Единица для сравнения: латинские обозначения переводятся в русские («kg·m» → «кгм»). */
function canonicalUnit(unit: unknown): string {
  return asText(unit)
    .replace(/[²³¹⁻]/g, (char) => SUPERSCRIPTS[char])
    .replace(/\^/g, '')
    .split('/')
    .map((part) => part
      .split(/[\s.*×⋅·]+/)
      .filter(Boolean)
      .map((token) => token.replace(/^([A-Za-zΩ]+)(-?\d*)$/, (_, base: string, power: string) => (LATIN_UNITS[base] ?? base) + power))
      .join(''))
    .join('/');
}

export function parseQuantity(text: unknown): Quantity | null {
  const source = asText(text).trim().replace(/[−–]/g, '-');
  const match = source.match(NUMBER_PREFIX);
  if (!match) return null;
  const raw = match[0].replace(/[   ]/g, '').replace(',', '.');
  const [mantissa, exponentText] = raw.toLowerCase().split('e');
  let exponent = exponentText ? Number(exponentText) : 0;
  let rest = source.slice(match[0].length);
  const power = rest.match(POWER_OF_TEN);
  if (power) {
    const digits = power[1] ?? power[2].replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]/g, (char) => SUPERSCRIPT_DIGITS[char]);
    exponent += Number(digits);
    rest = rest.slice(power[0].length);
  }
  const value = Number(mantissa) * 10 ** exponent;
  if (!Number.isFinite(value)) return null;
  // Точность записи: знаки после запятой в мантиссе с поправкой на степень («1.5e-3» → 4).
  const decimals = (mantissa.split('.')[1] || '').length - exponent;
  return { value, unit: rest.trim(), decimals };
}

/** «мПа» (милли) и «МПа» (мега) — разные единицы, остальное без учёта регистра. */
function sameUnit(left: string, right: string): boolean {
  if (left === right) return true;
  if (left.length > 1 && left.slice(1) === right.slice(1) && left[0] !== right[0] && /[мМmM]/.test(left[0]) && /[мМmM]/.test(right[0])) {
    return false;
  }
  return left.toLocaleLowerCase() === right.toLocaleLowerCase();
}

function allowedError(expected: Quantity, tolerance: AnswerSpec['tolerance']): number {
  const explicit = Number(tolerance);
  if (tolerance !== undefined && tolerance !== null && tolerance !== '' && Number.isFinite(explicit) && explicit >= 0 && explicit <= 0.5) {
    return Math.max(1e-9, Math.abs(expected.value) * explicit);
  }
  return 0.5 * 10 ** -expected.decimals + 1e-9;
}

function sameText(left: unknown, right: unknown): boolean {
  const clean = (value: unknown) => asText(value).trim().toLocaleLowerCase().replace(/\s+/g, ' ');
  return clean(left) !== '' && clean(left) === clean(right);
}

export function checkAnswer(answer: string, spec: AnswerSpec): AnswerCheck {
  if (NOT_A_NUMBER.test(asText(answer).trim())) return 'incorrect';
  const candidates = (Array.isArray(spec.correct) ? spec.correct : [spec.correct]).map(asText);
  if (candidates.some((candidate) => sameText(answer, candidate))) return 'correct';
  const mode = spec.mode ?? (spec.numeric ? 'equivalent' : 'form');
  if (mode === 'choice') return 'incorrect';
  if (mode === 'form' && candidates.some((candidate) => sameForm(answer, candidate))) return 'correct';
  if (mode === 'equivalent' && !spec.unit && candidates.some((candidate) => sameMath(answer, candidate, { numbers: Boolean(spec.numeric) }))) return 'correct';
  if (!spec.numeric) return 'incorrect';
  const given = parseQuantity(answer);
  if (!given || NOT_A_UNIT.test(normalizeUnit(given.unit))) return 'incorrect';
  let unitMismatch = false;
  for (const candidate of candidates) {
    const expected = parseQuantity(candidate);
    if (!expected || NOT_A_UNIT.test(normalizeUnit(expected.unit))) continue;
    if (Math.abs(given.value - expected.value) > allowedError(expected, spec.tolerance)) continue;
    const allowed = [spec.unit || expected.unit, ...(spec.acceptedUnits || [])].map(canonicalUnit).filter(Boolean);
    // Единицу можно не писать: поле ответа подсказывает, в чём ответ.
    if (!given.unit || !allowed.length || allowed.some((unit) => sameUnit(canonicalUnit(given.unit), unit))) return 'correct';
    unitMismatch = true;
  }
  return unitMismatch ? 'wrong_unit' : 'incorrect';
}
