/**
 * «Решаю по шагам»: ученик сам пишет каждую строку решения, строка сверяется с исходной задачей.
 * Выражение — строка равна исходному по смыслу. Уравнение — равносильно исходному: разность частей
 * отличается от исходной постоянным множителем (перенос слагаемых, деление на число). Деление на x
 * или возведение в квадрат меняет множество корней — такой шаг не засчитывается, и это правильно.
 */
import { evaluateMath, extractTask, latinLetters, parseExpression, sameForm, sameMath, variables, type MathNode } from './mathExpression';

export type StepSolverKind = 'expression' | 'equation';
export type SolverStep = { hint: string; expected: string };
export type SolverMistake = { wrong: string; message: string };
export type StepVerdict =
  | { status: 'ok'; done: boolean }
  | { status: 'mistake'; message: string }
  | { status: 'wrong' }
  | { status: 'unreadable' };

type Equation = { difference: MathNode; names: string[] };

const SAMPLES = [1.7, 2.3, 3.1, 0.6, 4.4, 1.2, 2.9, 5.3];

export function parseEquation(source: string): Equation | null {
  const sides = latinLetters(source).split('=');
  if (sides.length !== 2) return null;
  const left = parseExpression(sides[0]);
  const right = parseExpression(sides[1]);
  if (!left || !right) return null;
  const difference: MathNode = { kind: 'bin', op: '-', left, right };
  return { difference, names: [...variables(difference)] };
}

const ROOT_RANGE = 60;
const ROOT_GRID = 0.05;
const ZERO = 1e-9;

/**
 * Корни уравнения с одной переменной: смена знака на сетке (уточняем делением пополам)
 * и точные рациональные кандидаты p/q (двойные корни вроде (x − 2)² = 0 знак не меняют).
 * 'all' — тождество (0 = 0), null — переменных не одна.
 */
export function equationRoots(equation: Equation): number[] | 'all' | null {
  if (equation.names.length > 1) return null;
  const name = equation.names[0] ?? 'x';
  const f = (x: number) => evaluateMath(equation.difference, { [name]: x });
  if (SAMPLES.every((x) => Math.abs(f(x)) < ZERO) && Math.abs(f(-SAMPLES[0])) < ZERO) return 'all';
  const roots: number[] = [];
  const add = (x: number) => { if (!roots.some((root) => Math.abs(root - x) < 1e-6)) roots.push(x); };
  for (let q = 1; q <= 12; q += 1) {
    for (let p = -ROOT_RANGE * q; p <= ROOT_RANGE * q; p += 1) {
      const x = p / q;
      if (Math.abs(f(x)) < ZERO) add(x);
    }
  }
  let previous = f(-ROOT_RANGE);
  for (let x = -ROOT_RANGE + ROOT_GRID; x <= ROOT_RANGE; x += ROOT_GRID) {
    const current = f(x);
    if (Number.isFinite(previous) && Number.isFinite(current) && previous * current < 0) {
      let low = x - ROOT_GRID;
      let high = x;
      for (let step = 0; step < 60; step += 1) {
        const middle = (low + high) / 2;
        if (f(low) * f(middle) <= 0) high = middle; else low = middle;
      }
      const root = (low + high) / 2;
      // Разрыв (1/x около нуля) тоже меняет знак — корень только там, где значение действительно ~0.
      if (Math.abs(f(root)) < 1e-6) add(root);
    }
    previous = current;
  }
  return roots.sort((a, b) => a - b);
}

function sameRootSet(first: number[] | 'all' | null, second: number[] | 'all' | null): boolean {
  if (first === null || second === null) return false;
  if (first === 'all' || second === 'all') return first === second;
  return first.length === second.length && first.every((root, index) => Math.abs(root - second[index]) < 1e-6);
}

/**
 * Равносильны ли уравнения. Быстрый признак: f₂ = k·f₁ при постоянном k ≠ 0 (перенос, деление на число).
 * Иначе — у уравнения с одной переменной те же корни: так засчитываются умножение на общий знаменатель
 * и возведение в квадрат, если они не дали посторонних корней и не потеряли корни.
 */
export function sameEquation(first: Equation, second: Equation): boolean {
  if (proportional(first, second)) return true;
  const names = new Set([...first.names, ...second.names]);
  return names.size <= 1 && sameRootSet(equationRoots(first), equationRoots(second));
}

function proportional(first: Equation, second: Equation): boolean {
  const names = [...new Set([...first.names, ...second.names])];
  let ratio: number | null = null;
  let compared = 0;
  for (let round = 0; round < SAMPLES.length; round += 1) {
    const scope = Object.fromEntries(names.map((name, index) => [name, SAMPLES[(round + index * 3) % SAMPLES.length]]));
    const a = evaluateMath(first.difference, scope);
    const b = evaluateMath(second.difference, scope);
    if (!Number.isFinite(a) || !Number.isFinite(b)) continue;
    if (Math.abs(a) < 1e-9 || Math.abs(b) < 1e-9) {
      if (Math.abs(a) < 1e-9 !== Math.abs(b) < 1e-9) return false;
      continue;
    }
    const current = b / a;
    if (ratio === null) ratio = current;
    else if (Math.abs(current - ratio) > 1e-7 * Math.max(1, Math.abs(ratio))) return false;
    compared += 1;
  }
  return compared >= 2 && ratio !== null && Math.abs(ratio) > 1e-12;
}

/** Корни из записи «x = 2», «x = 1 или x = 3», «x₁ = 1; x₂ = 3». null — это не ответ-корни. */
export function parseRoots(source: string): number[] | null {
  const parts = latinLetters(source).split(/\s*(?:или|;|,(?=\s*[a-z]))\s*/i).filter(Boolean);
  const roots: number[] = [];
  for (const part of parts) {
    const match = /^\s*[a-z](?:_?\d|[₁₂])?\s*=\s*(.+)$/i.exec(part);
    const node = match ? parseExpression(match[1]) : null;
    if (!node || variables(node).size) return null;
    const value = evaluateMath(node, {});
    if (!Number.isFinite(value)) return null;
    roots.push(value);
  }
  return roots.length ? roots : null;
}

function rootsMatch(given: number[], expected: number[]): boolean {
  const sort = (values: number[]) => [...new Set(values.map((value) => Math.round(value * 1e9) / 1e9))].sort((a, b) => a - b);
  const a = sort(given);
  const b = sort(expected);
  return a.length === b.length && a.every((value, index) => Math.abs(value - b[index]) < 1e-7);
}

/** «любое число» → 'all', «нет корней» → 'none'. */
function specialAnswer(answers: string[]): 'all' | 'none' | null {
  const text = answers.join(' ').toLocaleLowerCase();
  if (/любое|бесконечно много|x\s*[—-]\s*любое/.test(text)) return 'all';
  if (/нет корней|корней нет|не имеет корней|решений нет|нет решений/.test(text)) return 'none';
  return null;
}

export type SolverSpec = {
  kind: StepSolverKind;
  start: string;
  finalAnswer: string[];
  answerMode?: 'form' | 'equivalent';
  mistakes?: SolverMistake[];
};

/** Проверить очередную строку решения ученика. */
export function checkStep(line: string, rawSpec: SolverSpec): StepVerdict {
  const spec = { ...rawSpec, start: extractTask(rawSpec.start) };
  let text = line.trim();
  if (!text) return { status: 'unreadable' };
  if (spec.kind === 'equation') {
    const start = parseEquation(spec.start);
    const expectedRoots = spec.finalAnswer.map(parseRoots).find(Boolean) ?? null;
    const roots = parseRoots(text);
    if (roots && expectedRoots) {
      if (rootsMatch(roots, expectedRoots)) return { status: 'ok', done: true };
      const named = mistakeOrWrong(text, spec);
      if (named.status === 'mistake') return named;
      // Все названные корни верны, но их меньше, чем нужно.
      const partial = roots.every((root) => expectedRoots.some((expected) => Math.abs(root - expected) < 1e-7));
      return partial ? { status: 'mistake', message: 'Найдены не все корни — проверь, не потерян ли корень.' } : named;
    }
    const special = specialAnswer(spec.finalAnswer);
    // Ответ словами: «любое число», «нет корней».
    if (special && start && specialAnswer([text]) === special) {
      const roots = equationRoots(start);
      const fits = special === 'all' ? roots === 'all' : Array.isArray(roots) && roots.length === 0;
      return fits ? { status: 'ok', done: true } : { status: 'wrong' };
    }
    const equation = parseEquation(text);
    if (!start || !equation) return { status: 'unreadable' };
    if (!sameEquation(start, equation)) return mistakeOrWrong(text, spec);
    // Переменная исчезла: 0 = 0 (любое число) или 0 = 5 (корней нет) — это и есть ответ.
    return { status: 'ok', done: Boolean(special) && equation.names.length === 0 };
  }
  // В тетради цепочку пишут «= 5x»: ведущий знак равенства не мешает.
  if (text.startsWith('=')) text = text.slice(1).trim();
  if (!text || !parseExpression(text)) return { status: 'unreadable' };
  if (!sameMath(text, spec.start)) return mistakeOrWrong(text, spec);
  const mode = spec.answerMode ?? 'form';
  const done = spec.finalAnswer.some((answer) => (mode === 'form' ? sameForm(text, answer) : sameMath(text, answer)));
  return { status: 'ok', done };
}

function mistakeOrWrong(text: string, spec: SolverSpec): StepVerdict {
  for (const mistake of spec.mistakes ?? []) {
    const hit = spec.kind === 'equation'
      ? (() => {
        const wrong = parseEquation(mistake.wrong);
        const given = parseEquation(text);
        return wrong && given ? sameEquation(wrong, given) : sameForm(text, mistake.wrong);
      })()
      : sameMath(text, mistake.wrong);
    if (hit) return { status: 'mistake', message: mistake.message };
  }
  return { status: 'wrong' };
}

/** Данные блока от модели: пропускаем пустые шаги и ошибки, ответ — всегда списком. */
export function normalizeSolver(content: {
  kind?: unknown; start?: unknown; steps?: unknown; final_answer?: unknown; answer_mode?: unknown; mistakes?: unknown;
}): (SolverSpec & { steps: SolverStep[] }) | null {
  const start = typeof content.start === 'string' ? extractTask(content.start) : '';
  const kind: StepSolverKind = content.kind === 'equation' || (content.kind !== 'expression' && start.includes('=')) ? 'equation' : 'expression';
  const steps = (Array.isArray(content.steps) ? content.steps : [])
    .filter((step): step is Record<string, unknown> => Boolean(step) && typeof step === 'object')
    .map((step) => ({ hint: String(step.hint ?? '').trim(), expected: String(step.expected ?? '').trim() }))
    .filter((step) => step.expected);
  const finalAnswer = (Array.isArray(content.final_answer) ? content.final_answer : [content.final_answer])
    .filter((answer): answer is string => typeof answer === 'string' && Boolean(answer.trim()));
  const mistakes = (Array.isArray(content.mistakes) ? content.mistakes : [])
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
    .map((item) => ({ wrong: String(item.wrong ?? '').trim(), message: String(item.message ?? '').trim() }))
    .filter((item) => item.wrong && item.message);
  if (!start || !finalAnswer.length) return null;
  const answerMode = content.answer_mode === 'equivalent' ? 'equivalent' : 'form';
  return { kind, start, steps, finalAnswer, answerMode, mistakes };
}
