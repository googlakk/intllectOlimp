/** The last submitted response, independent of grading and the optional tutor. */
export type SubmittedResponse = {
  value: string;
  outcome: 'correct' | 'incorrect' | 'wrong_unit' | 'assisted' | 'skipped';
  questionIndex?: number;
  variant?: string;
};

export type ResponseDetails = Record<string, SubmittedResponse>;
export type ResponseCaptureProps = { onResponse?: (response: SubmittedResponse) => void };

export function responseKey(blockIndex: number, questionIndex?: number): string {
  return questionIndex === undefined ? String(blockIndex) : `${blockIndex}_q${questionIndex}`;
}

/** Labels are captured from component state; answers are never scraped from rendered HTML. */
export function formatResponseLines(lines: readonly string[]): string {
  return lines.length ? lines.join('\n') : 'Ничего не выбрано';
}

export function formatResponsePairs(pairs: ReadonlyArray<readonly [string, string | undefined]>): string {
  return formatResponseLines(pairs.map(([label, value]) => `${label} → ${value || 'Не выбрано'}`));
}
