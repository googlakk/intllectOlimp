import { narrationSegments, narrationSpeechText } from './lessonContent';

export function narrationSentences(text: string): string[] {
  return narrationSegments(text, 360);
}

export function activeNarrationSentence(text: string, progress: number): string {
  const sentences = narrationSentences(text);
  if (sentences.length === 0) return '';
  const safeProgress = Math.max(0, Math.min(progress, 0.999999));
  return sentences[Math.floor(safeProgress * sentences.length)] || sentences[0];
}

/** Субтитры: короткие фразы (до ~90 знаков), длинное предложение делится по запятым. */
export function subtitleChunks(text: string): string[] {
  return narrationSegments(text, 90);
}

/** Фраза субтитров на текущий момент: каждая держится на экране пропорционально своей длине. */
export function activeSubtitle(text: string, progress: number): string {
  const chunks = subtitleChunks(text);
  if (chunks.length === 0) return '';
  const total = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  let position = Math.max(0, Math.min(progress, 0.999999)) * total;
  for (const chunk of chunks) {
    if (position < chunk.length) return chunk;
    position -= chunk.length;
  }
  return chunks[chunks.length - 1];
}

export { narrationSegments, narrationSpeechText };
