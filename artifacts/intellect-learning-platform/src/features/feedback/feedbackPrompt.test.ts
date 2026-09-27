import { beforeEach, describe, expect, it } from 'vitest';
import { feedbackAlreadyAsked, hasFeedback, rememberFeedbackAsked } from './feedbackPrompt';

const store = new Map<string, string>();
const localStorageStub = {
  getItem: (key: string) => store.get(key) ?? null,
  setItem: (key: string, value: string) => { store.set(key, value); },
  clear: () => store.clear(),
};

describe('lesson feedback prompt', () => {
  beforeEach(() => {
    (globalThis as { window?: unknown }).window = { localStorage: localStorageStub };
    store.clear();
  });

  it('asks once per lesson version', () => {
    expect(feedbackAlreadyAsked(9, 41)).toBe(false);
    rememberFeedbackAsked(9, 41);
    expect(feedbackAlreadyAsked(9, 41)).toBe(true);
    // Новая версия урока — новый вопрос.
    expect(feedbackAlreadyAsked(9, 42)).toBe(false);
  });

  it('treats a filled answer as feedback', () => {
    expect(hasFeedback(null, null, '  ')).toBe(false);
    expect(hasFeedback(4, null, '')).toBe(true);
    expect(hasFeedback(null, false, '')).toBe(true);
    expect(hasFeedback(null, null, 'Опечатка')).toBe(true);
  });
});
