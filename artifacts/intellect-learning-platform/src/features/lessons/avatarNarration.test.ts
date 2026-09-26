import { describe, expect, it } from 'vitest';
import { activeNarrationSentence, activeSubtitle, narrationSentences, narrationSpeechText, subtitleChunks } from './avatarNarration';

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

  it('cuts long sentences into short subtitle phrases timed by their length', () => {
    const text = 'Колонисты злились не только из-за денег, они возмущались, что законы для них принимают без их голоса. Итог.';
    const chunks = subtitleChunks(text);
    expect(chunks.every((chunk) => chunk.length <= 90)).toBe(true);
    expect(chunks.length).toBeGreaterThan(2);
    expect(activeSubtitle(text, 0)).toBe(chunks[0]);
    expect(activeSubtitle(text, 0.999)).toBe('Итог.');
  });

  it('does not pronounce markdown or latex commands', () => {
    expect(narrationSpeechText('**Корень:** $\\sqrt{64} = 8$')).toBe('Корень: квадратный корень из 64 равно 8');
  });
});
