import { describe, expect, it } from 'vitest';
import { isInstructionLanguage, languageLabel } from './languages';

describe('instruction languages', () => {
  it('accepts Russian, Kyrgyz and English only', () => {
    expect(['ru', 'ky', 'en'].every(isInstructionLanguage)).toBe(true);
    expect(isInstructionLanguage('de')).toBe(false);
  });

  it('labels unknown values as Russian, the platform default', () => {
    expect(languageLabel('en')).toBe('Английский');
    expect(languageLabel(undefined)).toBe('Русский');
  });
});
