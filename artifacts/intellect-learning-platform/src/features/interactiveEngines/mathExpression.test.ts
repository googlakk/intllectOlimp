import { describe, expect, it } from 'vitest';
import { mathLineToLatex, mathToLatex, parseMath, sameMath } from './mathExpression';

const latex = (text: string) => mathToLatex(parseMath(text)!);

describe('sameMath', () => {
  it.each([
    ['2√3', '√12'], ['√(x+1)^2', 'x+1'], ['(a-b)(a+b)', 'a^2-b^2'], ['2x+3x', '5x'], ['1/(√2)', '√2/2'], ['x^-1', '1/x'],
  ])('%s = %s', (left, right) => expect(sameMath(left, right)).toBe(true));

  it.each([
    ['√(a+b)', '√a+√b'], ['(a+b)^2', 'a^2+b^2'], ['2x', 'x^2'], ['√12', '3√2'],
  ])('%s ≠ %s', (left, right) => expect(sameMath(left, right)).toBe(false));

  it('rejects words, equations and broken input', () => {
    expect(parseMath('пять')).toBeNull();
    expect(parseMath('2x = 4 + y = 1')).toBeNull();
    expect(parseMath('(2+3')).toBeNull();
    expect(parseMath('')).toBeNull();
    // В предпросмотр попадает только разобранное дерево: разметка и команды не проходят.
    expect(parseMath('<img src=x onerror=alert(1)>')).toBeNull();
    expect(parseMath('\\href{javascript:alert(1)}{x}')).toBeNull();
  });
});

describe('mathToLatex', () => {
  it('shows fractions, roots and powers as in a notebook', () => {
    expect(latex('3/4')).toBe('\\frac{3}{4}');
    expect(latex('2sqrt(3)')).toBe('2\\sqrt{3}');
    expect(latex('(a+b)^2')).toBe('{\\left(a + b\\right)}^{2}');
    expect(latex('(x+1)/(x-1)')).toBe('\\frac{x + 1}{x - 1}');
    expect(latex('0,5x')).toBe('0,5x');
    expect(mathLineToLatex('3x - 6 = x + 4')).toBe('3x - 6 = x + 4');
    expect(mathLineToLatex('x = 0 или x = 3')).toBe('x = 0\\quad\\text{или}\\quad x = 3');
  });
});
