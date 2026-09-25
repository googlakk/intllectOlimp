import { createMachine } from 'xstate';
import { useMachine } from '@xstate/react';
import { useMemo, useState } from 'react';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { BlockImage, blockImage } from './BlockMedia';
import { normalizeText, type BlockResult } from '@/features/interactiveEngines/scoring';

export type PredictionOption = {
  id: string;
  label: string;
};

export type ObservationFrame = {
  label: string;
  value: string;
};

export interface PredictionLabProps {
  title: string;
  question: string;
  options: PredictionOption[];
  correct_prediction: string;
  observation_title: string;
  observations: ObservationFrame[];
  explanation: string;
  media?: unknown;
  onAnswer?: (isCorrect: boolean) => void;
}

const labMachine = createMachine({
  id: 'predictionLab',
  initial: 'predict',
  states: {
    predict: { on: { observe: 'observe' } },
    observe: { on: { explain: 'explain' } },
    explain: {},
  },
});

export default function PredictionLab({
  title,
  question,
  options,
  correct_prediction,
  observation_title,
  observations,
  explanation,
  media,
  onAnswer,
}: PredictionLabProps) {
  const [snapshot, send] = useMachine(labMachine);
  const [selected, setSelected] = useState('');
  const [result, setResult] = useState<BlockResult>('idle');
  const hasImage = Boolean(blockImage(media));
  const correct = useMemo(() => normalizeText(selected) === normalizeText(correct_prediction), [selected, correct_prediction]);

  const observe = () => {
    setResult(correct ? 'correct' : 'incorrect');
    onAnswer?.(correct);
    send({ type: 'observe' });
  };

  return (
    <BlockShell title={title} subtitle={question}>
      {/* Картинка показывает установку опыта: смотрим на неё и делаем прогноз. */}
      {snapshot.matches('predict') && (
        <div className={hasImage ? 'grid gap-4 md:grid-cols-[minmax(0,42%)_minmax(0,1fr)] md:items-center' : ''}>
          {hasImage && <BlockImage media={media} variant="side" />}
          <div className={`grid gap-3 ${hasImage ? '' : 'md:grid-cols-2'}`}>
            {options.map((option) => (
              <button
                key={option.id}
                onClick={() => setSelected(option.id)}
                className={`rounded-lg border p-4 text-left text-sm font-semibold transition ${selected === option.id ? 'border-primary bg-primary/10' : 'border-border bg-card hover:border-primary/30'}`}
              >
                <RichText text={option.label} inline />
              </button>
            ))}
          </div>
        </div>
      )}
      {/* После прогноза установка остаётся миниатюрой рядом с наблюдением. */}
      {!snapshot.matches('predict') && (
        <div className="rounded-xl border border-border bg-background p-5">
          <div className="mb-4 flex items-center gap-4">
            {hasImage && <BlockImage media={media} variant="thumb" />}
            <h4 className="text-sm font-bold uppercase tracking-wide text-primary"><RichText text={observation_title} inline /></h4>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            {observations.map((item) => (
              <div key={item.label} className="rounded-lg border border-border bg-muted/20 p-4">
                <div className="text-xs font-bold text-muted-foreground"><RichText text={item.label} inline /></div>
                <div className="mt-2 text-xl font-bold text-foreground"><RichText text={item.value} inline /></div>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="mt-5 flex justify-end">
        {snapshot.matches('predict') && <PrimaryAction onClick={observe} disabled={!selected}>Проверить прогноз</PrimaryAction>}
        {snapshot.matches('observe') && <PrimaryAction onClick={() => send({ type: 'explain' })}>Объяснить результат</PrimaryAction>}
      </div>
      <ResultPanel
        result={snapshot.matches('predict') ? 'idle' : result}
        correctText={snapshot.matches('explain') ? explanation : 'Прогноз совпал с наблюдением.'}
        incorrectText={snapshot.matches('explain') ? explanation : 'Наблюдение отличается от прогноза. Посмотрите на данные.'}
      />
    </BlockShell>
  );
}
