import { describe, expect, it } from 'vitest';

import { needsRichTextEngine } from './RichText';

describe('RichText fast path', () => {
  it('keeps plain classroom text on the lightweight renderer', () => {
    expect(needsRichTextEngine('Какое из следующих чисел является делителем числа 24?')).toBe(false);
    expect(needsRichTextEngine('5769')).toBe(false);
  });

  it('uses the full markdown renderer for authored formatting and math', () => {
    expect(needsRichTextEngine('**Важно:** проверь правило')).toBe(true);
    expect(needsRichTextEngine('sqrt(49) = 7')).toBe(true);
    expect(needsRichTextEngine('| a | b |\n|---|---|')).toBe(true);
  });
});
