import { describe, expect, it } from 'vitest';
import { calculateDensity, densityToSI } from './physicsContent';

describe('density experiment', () => {
  it('preserves density when mass and volume change by the same factor', () => {
    expect(calculateDensity(60, 20)).toBe(calculateDensity(120, 40));
    expect(calculateDensity(54, 20)).toBe(2.7);
  });
  it('converts grams per cubic centimetre to SI', () => {
    expect(densityToSI(calculateDensity(54, 20))).toBe(2700);
  });
  it('rejects impossible or unbounded experiment inputs', () => {
    expect(() => calculateDensity(60, 0)).toThrow(RangeError);
    expect(() => calculateDensity(-1, 20)).toThrow(RangeError);
    expect(() => calculateDensity(Infinity, 20)).toThrow(RangeError);
  });
});
