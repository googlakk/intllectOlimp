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

/**
 * График на всю ширину блока: по умолчанию Vega-Lite рисует его шириной 200 px, и на телефоне
 * он занимает треть экрана, а на компьютере — угол. Составные графики (concat, facet, repeat)
 * так растягивать нельзя — их оставляем как есть.
 */
function responsiveSpec(spec: DataInvestigationProps['vega_lite_spec']): DataInvestigationProps['vega_lite_spec'] {
  if (!spec || typeof spec !== 'object') return spec;
  const composite = ['hconcat', 'vconcat', 'concat', 'facet', 'repeat'].some((key) => key in spec);
  if (composite) return spec;
  return { height: 260, ...spec, width: 'container', autosize: { type: 'fit', contains: 'padding' } } as DataInvestigationProps['vega_lite_spec'];
}

export default function DataInvestigation({ title, description, vega_lite_spec, question, explanation, onAnswer }: DataInvestigationProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [selected, setSelected] = useState('');
  const [result, setResult] = useState<BlockResult>('idle');

  useEffect(() => {
    let view: Result | undefined;
    if (!containerRef.current) return undefined;
    embed(containerRef.current, responsiveSpec(vega_lite_spec), { actions: false, renderer: 'svg' })
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
      {/* Отступ — у обёртки: Vega меряет ширину контейнера вместе с padding и иначе вылезает за рамку. */}
      <div className="min-h-[320px] rounded-xl border border-border bg-background p-4">
        <div ref={containerRef} className="block w-full" />
      </div>
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
