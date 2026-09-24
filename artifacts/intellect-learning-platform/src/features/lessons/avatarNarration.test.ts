import { describe, expect, it } from 'vitest';
import { activeNarrationSentence, narrationSentences, narrationSpeechText } from './avatarNarration';

describe('avatar narration', () => {
  it('splits an explanation into readable phrases', () => {
    expect(narrationSentences('Первое правило. Затем пример! Теперь попробуйте?')).toEqual([
      'Первое правило.',
      'Затем пример!',
      'Теперь попробуйте?',
    ]);
  });

  it('selects a phrase using normalized playback progress', () => {
    const text = 'Один. Два. Три.';
    expect(activeNarrationSentence(text, 0)).toBe('Один.');
    expect(activeNarrationSentence(text, 0.5)).toBe('Два.');
    expect(activeNarrationSentence(text, 1)).toBe('Три.');
  });

  it('does not pronounce markdown or latex commands', () => {
    expect(narrationSpeechText('**Корень:** $\\sqrt{64} = 8$')).toBe('Корень: квадратный корень из 64 равно 8');
  });
});
