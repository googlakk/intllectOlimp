import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import {
  Background,
  ConnectionMode,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useNodesState,
  useReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { PrimaryAction, ResultPanel } from './shared';
import { linkKey } from '@/features/interactiveEngines/linkBoard';
import { resultFromScore, scoreLinks, type BlockResult, type LinkScore } from '@/features/interactiveEngines/scoring';

export type BoardNode = {
  id: string;
  content: ReactNode;
  position: { x: number; y: number };
  style?: CSSProperties;
};

const EDGE_COLORS = { idle: 'hsl(var(--primary))', correct: '#16a34a', wrong: 'hsl(var(--destructive))' };

const SIDES = [
  { id: 't', position: Position.Top },
  { id: 'r', position: Position.Right },
  { id: 'b', position: Position.Bottom },
  { id: 'l', position: Position.Left },
] as const;

/** Карточка с точками на всех сторонах: стрелка выходит с той, что смотрит на цель. */
function CardNode({ data }: NodeProps) {
  return (
    <>
      {SIDES.map((side) => (
        <Handle key={side.id} id={side.id} type="source" position={side.position} style={{ width: 8, height: 8, opacity: 0.35 }} />
      ))}
      {(data as { label: ReactNode }).label}
    </>
  );
}

const NODE_TYPES = { card: CardNode };

function center(node: Node | undefined) {
  const width = node?.measured?.width ?? 240;
  const height = node?.measured?.height ?? 80;
  return { x: (node?.position.x ?? 0) + width / 2, y: (node?.position.y ?? 0) + height / 2 };
}

export function pickSides(from: { x: number; y: number }, to: { x: number; y: number }): [string, string] {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? ['r', 'l'] : ['l', 'r'];
  return dy > 0 ? ['b', 't'] : ['t', 'b'];
}

function makeEdge(source: string, target: string, tone: keyof typeof EDGE_COLORS = 'idle'): Edge {
  const color = EDGE_COLORS[tone];
  return {
    id: linkKey(source, target),
    source,
    target,
    type: 'default',
    animated: tone === 'idle',
    style: { stroke: color, strokeWidth: 2 },
    markerEnd: { type: MarkerType.ArrowClosed, color, width: 18, height: 18 },
  };
}

/** Колонок столько, сколько помещается карточек нормального размера. */
export function columnsForWidth(width: number): number {
  if (width < 560) return 1;
  if (width < 820) return 2;
  return 3;
}

type LinkBoardProps = {
  /** Раскладка карточек под заданное число колонок. */
  layout: (columns: number) => BoardNode[];
  expected: Array<{ from: string; to: string }>;
  checkLabel: string;
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
};

/**
 * Доска для заданий «соедини стрелками». Соединить можно касанием (карточка,
 * затем следующая) или перетаскиванием от точки. Стрелка удаляется нажатием.
 */
export default function LinkBoard(props: LinkBoardProps) {
  return <ReactFlowProvider><Board {...props} /></ReactFlowProvider>;
}

function toFlowNodes(boardNodes: BoardNode[]): Node[] {
  return boardNodes.map((node) => ({
    id: node.id,
    position: node.position,
    type: 'card',
    data: { label: node.content },
    style: {
      borderRadius: 12, borderWidth: 1, borderStyle: 'solid', borderColor: 'hsl(var(--border))', background: 'hsl(var(--card))',
      padding: 10, cursor: 'pointer', ...node.style,
    },
  }));
}

function Board({ layout, expected, checkLabel, explanation, onAnswer }: LinkBoardProps) {
  const container = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(3);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>(toFlowNodes(layout(3)));
  const { fitView } = useReactFlow();

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    // Перестраиваем доску в следующем кадре: смена колонок меняет высоту, и
    // правка прямо в колбэке зацикливает ResizeObserver (ошибка в консоли).
    let frame = 0;
    const observer = new ResizeObserver(([entry]) => {
      const width = entry.contentRect.width;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setColumns(columnsForWidth(width)));
    });
    observer.observe(element);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    setNodes(toFlowNodes(layout(columns)));
    const frame = requestAnimationFrame(() => { void fitView({ padding: 0.12 }); });
    return () => cancelAnimationFrame(frame);
  }, [columns, layout, setNodes, fitView]);

  const rows = Math.ceil(nodes.length / columns) || 1;
  const narrow = columns === 1;
  const height = narrow ? rows * 170 + 40 : Math.max(360, rows * 190 + 80);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [pending, setPending] = useState<string | null>(null);
  const [summary, setSummary] = useState<LinkScore | null>(null);
  const [result, setResult] = useState<BlockResult>('idle');

  const clearCheck = () => {
    setSummary(null);
    setResult('idle');
  };

  const connect = (source: string, target: string) => {
    if (source === target) return;
    setEdges((current) => (current.some((edge) => edge.id === linkKey(source, target))
      ? current
      : [...current.map((edge) => makeEdge(edge.source, edge.target)), makeEdge(source, target)]));
    clearCheck();
  };

  const onNodeClick = (_event: unknown, node: Node) => {
    if (!pending) return setPending(node.id);
    if (pending !== node.id) connect(pending, node.id);
    setPending(null);
  };

  const removeEdge = (_event: unknown, edge: Edge) => {
    setEdges((current) => current.filter((item) => item.id !== edge.id).map((item) => makeEdge(item.source, item.target)));
    clearCheck();
  };

  const check = () => {
    const want = new Set(expected.map((link) => linkKey(link.from, link.to)));
    const score = scoreLinks(edges.map((edge) => edge.id), [...want]);
    setEdges((current) => current.map((edge) => makeEdge(edge.source, edge.target, want.has(edge.id) ? 'correct' : 'wrong')));
    setSummary(score);
    setResult(resultFromScore(score.score));
    setPending(null);
    onAnswer?.(score.score >= 80);
  };

  const reset = () => {
    setEdges([]);
    setPending(null);
    clearCheck();
  };

  const byId = new Map(nodes.map((node) => [node.id, node]));
  const displayEdges = edges.map((edge) => {
    const [sourceHandle, targetHandle] = pickSides(center(byId.get(edge.source)), center(byId.get(edge.target)));
    return { ...edge, sourceHandle, targetHandle };
  });

  const displayNodes = nodes.map((node) => (node.id === pending
    ? { ...node, style: { ...node.style, borderColor: 'hsl(var(--primary))', boxShadow: '0 0 0 3px hsl(var(--primary) / 0.35)' } }
    : node));

  return (
    <>
      <p className="mb-3 text-sm text-muted-foreground">
        {pending
          ? 'Теперь нажмите на карточку, к которой ведёт стрелка. Нажмите на ту же карточку, чтобы отменить.'
          : 'Нажмите на карточку, затем на следующую — появится стрелка. Нажмите на стрелку, чтобы удалить её.'}
      </p>
      <div ref={container} className="overflow-hidden rounded-xl border border-border bg-background" style={{ height }}>
        <ReactFlow
          nodes={displayNodes}
          edges={displayEdges}
          nodeTypes={NODE_TYPES}
          onNodesChange={onNodesChange}
          onConnect={(connection: Connection) => connection.source && connection.target && connect(connection.source, connection.target)}
          onNodeClick={onNodeClick}
          onEdgeClick={removeEdge}
          onPaneClick={() => setPending(null)}
          connectionMode={ConnectionMode.Loose}
          fitView
          fitViewOptions={{ padding: 0.12 }}
          panOnDrag={!narrow}
          zoomOnScroll={false}
          preventScrolling={false}
        >
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <div className="mt-5 flex flex-wrap items-center justify-end gap-3">
        {summary && (
          <p className="mr-auto text-sm font-semibold" role="status">
            Верных связей: {summary.correct} из {summary.correct + summary.missing}
            {summary.wrong > 0 && ` · лишних: ${summary.wrong}`}
          </p>
        )}
        <button type="button" onClick={reset} disabled={!edges.length} className="h-11 rounded-lg border border-border px-4 text-sm font-bold disabled:opacity-50">
          Сбросить связи
        </button>
        <PrimaryAction onClick={check} disabled={!edges.length}>{checkLabel}</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} partialText={explanation} incorrectText={explanation} />
    </>
  );
}
