import { createMachine } from 'xstate';
import { useMachine } from '@xstate/react';
import { useMemo, useState } from 'react';
import { BlockShell, ResultPanel } from './shared';
import { RichText } from './RichText';
import type { BlockResult } from '@/features/interactiveEngines/scoring';

export type ScenarioChoice = {
  label: string;
  next: string;
  feedback?: string;
};

export type ScenarioNode = {
  id: string;
  title: string;
  text: string;
  choices?: ScenarioChoice[];
  terminal?: boolean;
  success?: boolean;
};

export interface BranchingScenarioProps {
  title: string;
  context: string;
  start_node_id: string;
  nodes: ScenarioNode[];
  success_feedback: string;
  failure_feedback: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function BranchingScenario({
  title,
  context,
  start_node_id,
  nodes,
  success_feedback,
  failure_feedback,
  onAnswer,
}: BranchingScenarioProps) {
  const nodeById = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const machine = useMemo(() => createMachine({
    id: 'branchingScenario',
    initial: start_node_id,
    states: Object.fromEntries(nodes.map((node) => [
      node.id,
      {
        on: Object.fromEntries((node.choices || []).map((choice, index) => [
          `choose.${index}`,
          { target: choice.next },
        ])),
      },
    ])),
  }), [nodes, start_node_id]);
  const [snapshot, send] = useMachine(machine);
  const [lastFeedback, setLastFeedback] = useState('');
  const [result, setResult] = useState<BlockResult>('idle');
  const current = nodeById.get(String(snapshot.value)) || nodes[0];

  const choose = (choice: ScenarioChoice, index: number) => {
    setLastFeedback(choice.feedback || '');
    send({ type: `choose.${index}` });
    const next = nodeById.get(choice.next);
    if (next?.terminal) {
      const success = next.success === true;
      setResult(success ? 'correct' : 'incorrect');
      onAnswer?.(success);
    }
  };

  return (
    <BlockShell title={title} subtitle={context}>
      <div className="rounded-xl border border-border bg-muted/20 p-5">
        <p className="text-xs font-bold uppercase tracking-wide text-primary">Ситуация</p>
        <h4 className="mt-2 text-lg font-bold text-foreground"><RichText text={current.title} inline /></h4>
        <RichText text={current.text} className="mt-3 text-sm leading-relaxed text-muted-foreground" />
        {lastFeedback && (
          <div className="mt-4 rounded-lg border border-primary/20 bg-primary/10 p-3 text-sm font-medium text-foreground">
            <RichText text={lastFeedback} />
          </div>
        )}
      </div>
      {!current.terminal && (
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {(current.choices || []).map((choice, index) => (
            <button
              key={`${choice.label}-${index}`}
              onClick={() => choose(choice, index)}
              className="rounded-lg border border-border bg-card p-4 text-left text-sm font-semibold text-foreground shadow-sm transition hover:border-primary/50 hover:bg-primary/5"
            >
              <RichText text={choice.label} inline />
            </button>
          ))}
        </div>
      )}
      <ResultPanel
        result={result}
        correctText={success_feedback}
        incorrectText={failure_feedback}
      />
    </BlockShell>
  );
}
