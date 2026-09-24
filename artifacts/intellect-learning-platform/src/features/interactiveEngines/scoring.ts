export type BlockResult = 'idle' | 'correct' | 'incorrect' | 'partial';

export function normalizeText(value: unknown): string {
  return String(value ?? '').trim().toLocaleLowerCase();
}

export function sameSet(left: string[], right: string[]): boolean {
  const a = left.map(normalizeText).sort();
  const b = right.map(normalizeText).sort();
  return a.length === b.length && a.every((item, index) => item === b[index]);
}

export function scoreRatio(correct: number, total: number): number {
  if (total <= 0) return 0;
  return Math.round((correct / total) * 100);
}

export function resultFromScore(score: number): BlockResult {
  if (score >= 80) return 'correct';
  if (score > 0) return 'partial';
  return 'incorrect';
}

export function resultClasses(result: BlockResult): string {
  if (result === 'correct') return 'border-green-500/30 bg-green-500/10 text-green-700 dark:text-green-300';
  if (result === 'partial') return 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300';
  if (result === 'incorrect') return 'border-destructive/30 bg-destructive/10 text-destructive';
  return 'border-border bg-muted/20 text-muted-foreground';
}
