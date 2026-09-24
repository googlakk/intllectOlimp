import { useMemo, useState } from 'react';
import { ReactFlow, Background, Controls, addEdge, useEdgesState, useNodesState, type Connection, type Edge, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { resultFromScore, sameSet, scoreRatio, type BlockResult } from '@/features/interactiveEngines/scoring';

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

export default function ProcessBuilder({ title, instruction, steps, correct_edges, explanation, onAnswer }: ProcessBuilderProps) {
  const initialNodes = useMemo<Node[]>(() => steps.map((step, index) => ({
    id: step.id,
    position: { x: (index % 3) * 230, y: Math.floor(index / 3) * 140 },
    data: { label: <RichText text={`${step.label}${step.description ? `\n\n${step.description}` : ''}`} /> },
    style: { width: 190, whiteSpace: 'pre-wrap', borderRadius: 12, borderColor: 'hsl(var(--border))' },
  })), [steps]);
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [result, setResult] = useState<BlockResult>('idle');

  const onConnect = (connection: Connection) => {
    setEdges((current) => addEdge({ ...connection, animated: true, type: 'smoothstep' }, current));
  };

  const check = () => {
    const expected = correct_edges.map((edge) => `${edge.from}->${edge.to}`);
    const actual = edges.map((edge) => `${edge.source}->${edge.target}`);
    const correct = actual.filter((edge) => expected.includes(edge)).length;
    const score = sameSet(actual, expected) ? 100 : scoreRatio(correct, expected.length);
    const next = resultFromScore(score);
    setResult(next);
    onAnswer?.(score >= 80);
  };

  return (
    <BlockShell title={title} subtitle={instruction}>
      <div className="h-[440px] overflow-hidden rounded-xl border border-border bg-background">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          fitView
        >
          <Background />
          <Controls />
        </ReactFlow>
      </div>
      <div className="mt-5 flex justify-end">
        <PrimaryAction onClick={check}>Проверить схему</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} partialText={explanation} incorrectText={explanation} />
    </BlockShell>
  );
}
