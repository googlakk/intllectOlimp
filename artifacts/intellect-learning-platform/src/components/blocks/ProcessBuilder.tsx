import { useCallback, useMemo } from 'react';
import { BlockShell } from './shared';
import { RichText } from './RichText';
import LinkBoard, { type BoardNode } from './LinkBoard';
import { boardOrder } from '@/features/interactiveEngines/linkBoard';

export type ProcessStep = {
  id: string;
  label: string;
  description?: string;
};

export type ProcessEdge = {
  from: string;
  to: string;
  label?: string;
};

export interface ProcessBuilderProps {
  title: string;
  instruction: string;
  steps: ProcessStep[];
  correct_edges: ProcessEdge[];
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

const NODE_WIDTH = 240;

export default function ProcessBuilder({ title, instruction, steps, correct_edges, explanation, onAnswer }: ProcessBuilderProps) {
  const ordered = useMemo(() => boardOrder(steps), [steps]);
  const layout = useCallback((columns: number): BoardNode[] => ordered.map((step, index) => ({
    id: step.id,
    position: { x: (index % columns) * (NODE_WIDTH + 70), y: Math.floor(index / columns) * (columns === 1 ? 170 : 190) },
    style: { width: NODE_WIDTH, textAlign: 'left' },
    content: (
      <div>
        <div className="text-sm font-semibold leading-snug text-foreground"><RichText text={step.label} inline /></div>
        {step.description && <div className="mt-1.5 text-xs leading-snug text-muted-foreground"><RichText text={step.description} inline /></div>}
      </div>
    ),
  })), [ordered]);

  return (
    <BlockShell title={title} subtitle={instruction}>
      <LinkBoard key={ordered.map((step) => step.id).join('|')} layout={layout} expected={correct_edges} checkLabel="Проверить схему" explanation={explanation} onAnswer={onAnswer} />
    </BlockShell>
  );
}
