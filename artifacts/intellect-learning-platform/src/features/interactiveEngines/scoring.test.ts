import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { checkAnswer, normalizeUnit, parseQuantity, type AnswerSpec } from './scoring';

type Case = { answer: string; spec: AnswerSpec; expected: string; note: string };
// Общий набор с сервером (backend/services/assessment.py): правила должны совпадать.
const shared = JSON.parse(readFileSync(resolve(__dirname, '../../../../../backend/fixtures/answer_check_cases.json'), 'utf8')) as { cases: Case[] };

describe('checkAnswer', () => {
  it.each(shared.cases)('$note: «$answer» → $expected', ({ answer, spec, expected }) => {
    expect(checkAnswer(answer, spec)).toBe(expected);
  });

  it('parses quantities with their precision and normalizes units', () => {
    expect(parseQuantity('12,5 Н')).toEqual({ value: 12.5, unit: 'Н', decimals: 1 });
    expect(parseQuantity('1,5·10⁻³ м')).toMatchObject({ unit: 'м', decimals: 4 });
    expect(parseQuantity('1,5·10⁻³ м')!.value).toBeCloseTo(0.0015, 12);
    expect(parseQuantity('абв')).toBeNull();
    expect(normalizeUnit('Н · м / с²')).toBe('Нм/с2');
  });
});
