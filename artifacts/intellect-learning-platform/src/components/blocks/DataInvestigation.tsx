import embed, { type Result } from 'vega-embed';
import { useEffect, useRef, useState } from 'react';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { normalizeText, type BlockResult } from '@/features/interactiveEngines/scoring';

export type DataQuestion = {
  question: string;
  options: string[];
  correct_answer: string;
};

export interface DataInvestigationProps {
  title: string;
  description: string;
  vega_lite_spec: Record<string, unknown>;
  question: DataQuestion;
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function DataInvestigation({ title, description, vega_lite_spec, question, explanation, onAnswer }: DataInvestigationProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [selected, setSelected] = useState('');
  const [result, setResult] = useState<BlockResult>('idle');

  useEffect(() => {
    let view: Result | undefined;
    if (!containerRef.current) return undefined;
    embed(containerRef.current, vega_lite_spec, { actions: false, renderer: 'svg' })
      .then((resultView) => { view = resultView; })
      .catch(() => {
        if (containerRef.current) {
          containerRef.current.textContent = 'Не удалось отобразить визуализацию.';
        }
      });
    return () => view?.finalize();
  }, [vega_lite_spec]);

  const check = () => {
    const ok = normalizeText(selected) === normalizeText(question.correct_answer);
    setResult(ok ? 'correct' : 'incorrect');
    onAnswer?.(ok);
  };

  return (
    <BlockShell title={title} subtitle={description}>
      <div ref={containerRef} className="min-h-[320px] rounded-xl border border-border bg-background p-4" />
      <div className="mt-5 rounded-lg border border-border bg-muted/20 p-4">
        <h4 className="mb-3 text-sm font-bold text-foreground"><RichText text={question.question} inline /></h4>
        <div className="grid gap-2 md:grid-cols-2">
          {question.options.map((option) => (
            <button
              key={option}
              onClick={() => setSelected(option)}
              className={`rounded-lg border p-3 text-left text-sm font-semibold transition ${selected === option ? 'border-primary bg-primary/10' : 'border-border bg-card hover:border-primary/30'}`}
            >
              <RichText text={option} inline />
            </button>
          ))}
        </div>
      </div>
      <div className="mt-5 flex justify-end">
        <PrimaryAction onClick={check} disabled={!selected}>Проверить вывод</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} incorrectText={explanation} />
    </BlockShell>
  );
}
