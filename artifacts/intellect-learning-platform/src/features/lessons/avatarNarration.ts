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

export { narrationSegments, narrationSpeechText };
