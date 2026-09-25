import { describe, expect, it } from 'vitest';

import { boardOrder, linkKey } from './linkBoard';
import { scoreLinks } from './scoring';

const steps = ['read', 'fact', 'concept', 'law', 'theory', 'write'].map((id) => ({ id }));

describe('boardOrder', () => {
  it('never shows steps in the correct order', () => {
    expect(boardOrder(steps).map((step) => step.id)).not.toEqual(steps.map((step) => step.id));
  });

  it('is stable between renders and keeps every step', () => {
    expect(boardOrder(steps)).toEqual(boardOrder(steps));
    expect(boardOrder(steps).map((step) => step.id).sort()).toEqual(steps.map((step) => step.id).sort());
  });

  it('handles tiny boards', () => {
    expect(boardOrder([{ id: 'a' }, { id: 'b' }]).map((step) => step.id)).toEqual(['b', 'a']);
  });
});

describe('scoreLinks', () => {
  const expected = [linkKey('a', 'b'), linkKey('b', 'c'), linkKey('c', 'd')];

  it('gives full score for exact answer', () => {
    expect(scoreLinks(expected, expected)).toEqual({ correct: 3, wrong: 0, missing: 0, score: 100 });
  });

  it('penalises connecting everything to everything', () => {
    const all = ['a', 'b', 'c', 'd'].flatMap((from) => ['a', 'b', 'c', 'd'].filter((to) => to !== from).map((to) => linkKey(from, to)));
    expect(scoreLinks(all, expected).score).toBe(0);
  });

  it('counts partial answers and ignores duplicates', () => {
    expect(scoreLinks([linkKey('a', 'b'), linkKey('a', 'b'), linkKey('c', 'b')], expected)).toEqual({ correct: 1, wrong: 1, missing: 2, score: 0 });
    expect(scoreLinks([linkKey('a', 'b'), linkKey('b', 'c')], expected).score).toBe(67);
  });
});
