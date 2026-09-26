import { describe, expect, it } from 'vitest';
import { mathToLatex } from './mathExpression';
import { normalizeExplorer, reachedTarget, sampleCurve, substituteParams } from './functionExplorer';

const linear = normalizeExplorer({
  formula: 'y = k*x + b',
  params: [{ name: 'k', label: 'k', min: -3, max: 3, step: 0.5, default: 1 }, { name: 'b', label: 'b', min: -4, max: 4, step: 1, default: 0 }],
  target: { params: { k: 2, b: -1 } },
})!;

describe('normalizeExplorer', () => {
  it('reads formula, params and target', () => {
    expect(linear.params.map((param) => param.name)).toEqual(['k', 'b']);
    expect(linear.target).toEqual({ k: 2, b: -1 });
  });
  it('rejects unknown letters and broken formulas', () => {
    expect(normalizeExplorer({ formula: 'k*x + c', params: [{ name: 'k', min: 0, max: 1 }] })).toBeNull();
    expect(normalizeExplorer({ formula: 'y = (x' })).toBeNull();
  });
});

describe('sampleCurve', () => {
  it('breaks the hyperbola at zero and skips √x for negative x', () => {
    const hyperbola = normalizeExplorer({ formula: 'k/x', params: [{ name: 'k', min: 1, max: 4, default: 2 }] })!;
    expect(sampleCurve(hyperbola.formula, { k: 2 }, [-6, 6], [-6, 6])).toHaveLength(2);
    const root = normalizeExplorer({ formula: '√x' })!;
    const [segment] = sampleCurve(root.formula, {}, [-6, 6], [-6, 6]);
    expect(segment[0].x).toBeGreaterThanOrEqual(0);
  });
});

describe('target and labels', () => {
  it('matches sliders within half a step', () => {
    expect(reachedTarget({ k: 2, b: -1 }, linear.target, linear.params)).toBe(true);
    expect(reachedTarget({ k: 1.5, b: -1 }, linear.target, linear.params)).toBe(false);
  });
  it('substitutes values into the formula', () => {
    expect(mathToLatex(substituteParams(linear.formula, { k: 2, b: -1 }))).toBe('2x - 1');
    expect(mathToLatex(substituteParams(linear.formula, { k: -0.5, b: 3 }))).toBe('-0,5x + 3');
  });
});
