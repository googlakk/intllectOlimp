import { useMemo, useState } from 'react';
import type React from 'react';
import { ReactFlow, Background, Controls, addEdge, useEdgesState, useNodesState, type Connection, type Edge, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { resultFromScore, scoreRatio, type BlockResult } from '@/features/interactiveEngines/scoring';

export type ArgumentNode = {
  id: string;
  label: string;
  kind: 'claim' | 'evidence' | 'reasoning' | 'counterargument';
};

export interface ArgumentMapProps {
  title: string;
  prompt: string;
  nodes: ArgumentNode[];
  correct_links: Array<{ from: string; to: string }>;
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

const KIND_STYLE: Record<ArgumentNode['kind'], React.CSSProperties> = {
  claim: { background: 'hsl(var(--primary) / 0.12)', borderColor: 'hsl(var(--primary))' },
  evidence: { background: 'hsl(var(--card))', borderColor: 'hsl(var(--border))' },
  reasoning: { background: 'hsl(var(--muted) / 0.45)', borderColor: 'hsl(var(--border))' },
  counterargument: { background: 'hsl(var(--destructive) / 0.08)', borderColor: 'hsl(var(--destructive) / 0.35)' },
};

export default function ArgumentMap({ title, prompt, nodes: argumentNodes, correct_links, explanation, onAnswer }: ArgumentMapProps) {
  const initialNodes = useMemo<Node[]>(() => argumentNodes.map((node, index) => ({
    id: node.id,
    position: {
      x: node.kind === 'claim' ? 340 : (index % 2) * 520,
      y: node.kind === 'claim' ? 40 : 150 + Math.floor(index / 2) * 120,
    },
    data: { label: <RichText text={node.label} inline /> },
    style: { width: 220, borderRadius: 12, whiteSpace: 'pre-wrap', ...KIND_STYLE[node.kind] },
  })), [argumentNodes]);
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [result, setResult] = useState<BlockResult>('idle');

  const onConnect = (connection: Connection) => {
    setEdges((current) => addEdge({ ...connection, animated: true, type: 'smoothstep' }, current));
  };

  const check = () => {
    const expected = correct_links.map((link) => `${link.from}->${link.to}`);
    const actual = edges.map((edge) => `${edge.source}->${edge.target}`);
    const correct = actual.filter((edge) => expected.includes(edge)).length;
    const score = scoreRatio(correct, expected.length);
    const next = resultFromScore(score);
    setResult(next);
    onAnswer?.(score >= 80);
  };

  return (
    <BlockShell title={title} subtitle={prompt}>
      <div className="mb-3 flex flex-wrap gap-2 text-xs font-semibold">
        <span className="rounded-full bg-primary/10 px-2 py-1 text-primary">тезис</span>
        <span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">доказательство</span>
        <span className="rounded-full bg-destructive/10 px-2 py-1 text-destructive">контраргумент</span>
      </div>
      <div className="h-[460px] overflow-hidden rounded-xl border border-border bg-background">
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
        <PrimaryAction onClick={check}>Проверить аргумент</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} partialText={explanation} incorrectText={explanation} />
    </BlockShell>
  );
}
