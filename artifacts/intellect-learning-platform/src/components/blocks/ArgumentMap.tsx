import { useCallback, useMemo } from 'react';
import type React from 'react';
import { BlockShell } from './shared';
import { RichText } from './RichText';
import LinkBoard, { type BoardNode } from './LinkBoard';
import { boardOrder } from '@/features/interactiveEngines/linkBoard';

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

const NODE_WIDTH = 230;
const GAP = 60;

export default function ArgumentMap({ title, prompt, nodes: argumentNodes, correct_links, explanation, onAnswer }: ArgumentMapProps) {
  // Тезисы сверху, остальные карточки перемешаны ниже — раскладка не подсказывает связи.
  const claims = useMemo(() => argumentNodes.filter((node) => node.kind === 'claim'), [argumentNodes]);
  const others = useMemo(() => boardOrder(argumentNodes.filter((node) => node.kind !== 'claim')), [argumentNodes]);
  const layout = useCallback((columns: number): BoardNode[] => {
    const rowWidth = columns * NODE_WIDTH + (columns - 1) * GAP;
    const perRow = Math.min(columns, Math.max(claims.length, 1));
    const claimRows = Math.ceil(claims.length / perRow);
    const place = (node: ArgumentNode, position: BoardNode['position']): BoardNode => ({
      id: node.id,
      position,
      style: { width: NODE_WIDTH, ...KIND_STYLE[node.kind] },
      content: <div className="text-sm leading-snug text-foreground"><RichText text={node.label} inline /></div>,
    });
    const claimStart = (rowWidth - (perRow * NODE_WIDTH + (perRow - 1) * GAP)) / 2;
    return [
      ...claims.map((node, index) => place(node, {
        x: claimStart + (index % perRow) * (NODE_WIDTH + GAP),
        y: Math.floor(index / perRow) * 170,
      })),
      ...others.map((node, index) => place(node, {
        x: (index % columns) * (NODE_WIDTH + GAP),
        y: claimRows * 170 + 30 + Math.floor(index / columns) * 170,
      })),
    ];
  }, [claims, others]);

  return (
    <BlockShell title={title} subtitle={prompt}>
      <div className="mb-3 flex flex-wrap gap-2 text-xs font-semibold">
        <span className="rounded-full bg-primary/10 px-2 py-1 text-primary">тезис</span>
        <span className="rounded-full bg-muted px-2 py-1 text-muted-foreground">доказательство</span>
        <span className="rounded-full bg-destructive/10 px-2 py-1 text-destructive">контраргумент</span>
      </div>
      <LinkBoard key={argumentNodes.map((node) => node.id).join('|')} layout={layout} expected={correct_links} checkLabel="Проверить аргумент" explanation={explanation} onAnswer={onAnswer} />
    </BlockShell>
  );
}
