import { CheckCircle2, XCircle } from 'lucide-react';
import type React from 'react';
import { parseMathText } from './ShortExplanation';
import { RichText } from './RichText';
import { resultClasses, type BlockResult } from '@/features/interactiveEngines/scoring';

export function BlockShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="my-6 rounded-xl border border-border bg-card p-6 shadow-sm">
      <div className="mb-5">
        <h3 className="text-lg font-semibold text-foreground"><RichText text={title} inline /></h3>
        {subtitle && <div className="mt-2 text-sm leading-relaxed text-muted-foreground">{parseMathText(subtitle)}</div>}
      </div>
      {children}
    </section>
  );
}

export function ResultPanel({
  result,
  correctText,
  incorrectText,
  partialText,
}: {
  result: BlockResult;
  correctText?: string;
  incorrectText?: string;
  partialText?: string;
}) {
  if (result === 'idle') return null;
  const Icon = result === 'correct' ? CheckCircle2 : XCircle;
  const text = result === 'correct'
    ? correctText || 'Верно. Действие засчитано.'
    : result === 'partial'
      ? partialText || 'Часть выполнена верно. Проверьте оставшиеся элементы.'
      : incorrectText || 'Пока неверно. Попробуйте ещё раз.';
  return (
    <div className={`mt-5 flex items-start gap-3 rounded-lg border p-4 text-sm font-medium ${resultClasses(result)}`}>
      <Icon className="mt-0.5 h-5 w-5 shrink-0" />
      <div>{parseMathText(text)}</div>
    </div>
  );
}

export function PrimaryAction({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center justify-center rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}
