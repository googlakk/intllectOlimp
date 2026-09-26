import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { checkStep, normalizeSolver, parseRoots, type SolverSpec } from './stepSolver';

const expression: SolverSpec = {
  kind: 'expression', start: '√12 + √27', finalAnswer: ['5√3'],
  mistakes: [{ wrong: '√39', message: 'Корень из суммы не равен сумме корней.' }],
};
const linear: SolverSpec = { kind: 'equation', start: '3(x - 2) = x + 4', finalAnswer: ['x = 5'] };
const quadratic: SolverSpec = {
  kind: 'equation', start: 'x^2 = 3x', finalAnswer: ['x = 0 или x = 3'],
  mistakes: [{ wrong: 'x = 3', message: 'Делить на x нельзя: потерян корень x = 0.' }],
};

describe('checkStep — выражения', () => {
  it('accepts equal intermediate lines and finishes on the required form', () => {
    expect(checkStep('2√3 + 3√3', expression)).toEqual({ status: 'ok', done: false });
    expect(checkStep('5√3', expression)).toEqual({ status: 'ok', done: true });
    expect(checkStep('√75', expression)).toEqual({ status: 'ok', done: false });
  });
  it('names a known mistake and rejects other wrong lines', () => {
    expect(checkStep('√39', expression)).toEqual({ status: 'mistake', message: 'Корень из суммы не равен сумме корней.' });
    expect(checkStep('6√3', expression)).toEqual({ status: 'wrong' });
    expect(checkStep('пять корней', expression)).toEqual({ status: 'unreadable' });
  });
});

describe('checkStep — уравнения', () => {
  it('accepts equivalent transformations', () => {
    expect(checkStep('3x - 6 = x + 4', linear)).toEqual({ status: 'ok', done: false });
    expect(checkStep('2x = 10', linear)).toEqual({ status: 'ok', done: false });
    expect(checkStep('x = 5', linear)).toEqual({ status: 'ok', done: true });
  });
  it('rejects a sign error when moving terms', () => {
    expect(checkStep('3x - 6 = x - 4', linear).status).toBe('wrong');
    expect(checkStep('x = 4', linear).status).toBe('wrong');
  });
  it('catches the lost root after dividing by x', () => {
    expect(checkStep('x^2 - 3x = 0', quadratic)).toEqual({ status: 'ok', done: false });
    expect(checkStep('x(x - 3) = 0', quadratic)).toEqual({ status: 'ok', done: false });
    expect(checkStep('x = 3', quadratic)).toEqual({ status: 'mistake', message: 'Делить на x нельзя: потерян корень x = 0.' });
    expect(checkStep('x = 3 или x = 0', quadratic)).toEqual({ status: 'ok', done: true });
  });
});

describe('checkStep — дробные уравнения, корни, тождества', () => {
  it('accepts multiplying by the denominator and squaring when roots are kept', () => {
    const fraction: SolverSpec = { kind: 'equation', start: '1/x = 1', finalAnswer: ['x = 1'] };
    expect(checkStep('1 = x', fraction)).toEqual({ status: 'ok', done: false });
    const radical: SolverSpec = { kind: 'equation', start: '√x = 2', finalAnswer: ['x = 4'] };
    expect(checkStep('x = 4', radical)).toEqual({ status: 'ok', done: true });
    const shifted: SolverSpec = { kind: 'equation', start: '(x+1)/(x-2) = 2', finalAnswer: ['x = 5'] };
    expect(checkStep('x + 1 = 2(x - 2)', shifted)).toEqual({ status: 'ok', done: false });
  });
  it('rejects a squaring that brings an extraneous root', () => {
    const spec: SolverSpec = { kind: 'equation', start: '√(x+2) = x', finalAnswer: ['x = 2'] };
    expect(checkStep('x + 2 = x^2', spec).status).toBe('wrong');
  });
  it('says when a root is missing', () => {
    const spec: SolverSpec = { kind: 'equation', start: 'x^2 = 9', finalAnswer: ['x = 3 или x = -3'] };
    expect(checkStep('x = 3', spec)).toEqual({ status: 'mistake', message: 'Найдены не все корни — проверь, не потерян ли корень.' });
    expect(checkStep('x = -3 или x = 3', spec)).toEqual({ status: 'ok', done: true });
  });
  it('treats identities as equivalent to each other', () => {
    const spec: SolverSpec = { kind: 'equation', start: '2(x + 1) = 2x + 2', finalAnswer: ['любое число'] };
    expect(checkStep('2x + 2 = 2x + 2', spec)).toEqual({ status: 'ok', done: false });
    expect(checkStep('0 = 0', spec)).toEqual({ status: 'ok', done: true });
    expect(checkStep('x — любое число', spec)).toEqual({ status: 'ok', done: true });
    const none: SolverSpec = { kind: 'equation', start: 'x + 1 = x + 3', finalAnswer: ['нет корней'] };
    expect(checkStep('1 = 3', none)).toEqual({ status: 'ok', done: true });
    expect(checkStep('0 = 0', none).status).toBe('wrong');
  });
});

describe('parseRoots and normalizeSolver', () => {
  it('reads root lists', () => {
    expect(parseRoots('x₁ = 1; x₂ = 3')).toEqual([1, 3]);
    expect(parseRoots('x = -1/2')).toEqual([-0.5]);
    expect(parseRoots('2x = 4')).toBeNull();
  });
  it('drops broken model data', () => {
    expect(normalizeSolver({ start: '', final_answer: '1' })).toBeNull();
    const spec = normalizeSolver({ start: '2x = 4', final_answer: 'x = 2', steps: [{ hint: 'Делим', expected: 'x = 2' }, {}] });
    expect(spec).toMatchObject({ kind: 'equation', finalAnswer: ['x = 2'], steps: [{ hint: 'Делим', expected: 'x = 2' }] });
  });
});

type SharedCase = { kind: 'expression' | 'equation'; start: string; final_answer: string[]; answer_mode?: 'form' | 'equivalent'; line: string; status: string; done: boolean; note: string };
// Общий набор с сервером (backend/services/math_expression.py): строки решения проверяются одинаково.
const shared = JSON.parse(readFileSync(resolve(__dirname, '../../../../../backend/fixtures/step_solver_cases.json'), 'utf8')) as { cases: SharedCase[] };

describe('shared step cases', () => {
  it.each(shared.cases)('$note: «$line» → $status', (item) => {
    const verdict = checkStep(item.line, { kind: item.kind, start: item.start, finalAnswer: item.final_answer, answerMode: item.answer_mode });
    // Сервер не различает названную ошибку и просто неверную строку.
    const status = verdict.status === 'mistake' ? 'wrong' : verdict.status;
    expect({ status, done: verdict.status === 'ok' && verdict.done }).toEqual({ status: item.status, done: item.done });
  });
});
