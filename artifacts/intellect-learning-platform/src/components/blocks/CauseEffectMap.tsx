import { useEffect, useMemo, useRef, useState } from 'react';
import { MarkerType, Position, ReactFlow, ReactFlowProvider, useReactFlow, type Edge, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { resultFromScore, type BlockResult } from '@/features/interactiveEngines/scoring';
import {
  CAUSE_ROLES, KIND_LABELS, ROLE_LABELS, causeScore, checkFactors, diagramLayout, normalizeFactors,
  type CauseRole, type CauseVerdict,
} from '@/features/interactiveEngines/causeEffect';

export interface CauseEffectMapProps {
  title: string;
  instruction: string;
  event: { label: string; year?: string | number } | string;
  factors: unknown;
  explanation?: string;
  onAnswer?: (isCorrect: boolean) => void;
}

const PASS_SCORE = 80;
const TONES = { idle: 'hsl(var(--primary))', ok: '#16a34a', bad: 'hsl(var(--destructive))', trigger: '#d97706' };
const CARD = { borderRadius: 12, border: '1px solid hsl(var(--border))', background: 'hsl(var(--card))', padding: 10, fontSize: 12, width: 210 };

/** Схема только показывает выбор ученика: причины → событие → последствия. */
function Diagram({ eventLabel, factors, chosen, verdicts }: {
  eventLabel: string; factors: ReturnType<typeof normalizeFactors>; chosen: Record<string, CauseRole | undefined>; verdicts: CauseVerdict[] | null;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const { fitView } = useReactFlow();
  useEffect(() => {
    if (!box.current) return;
    let frame = 0;
    const observer = new ResizeObserver(([entry]) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setWidth(entry.contentRect.width));
    });
    observer.observe(box.current);
    return () => { cancelAnimationFrame(frame); observer.disconnect(); };
  }, []);
  const { positions, height } = diagramLayout(chosen, factors.map((factor) => factor.id), width);
  // Стрелки идут слева направо (на узком экране — сверху вниз), без петель вокруг карточек.
  const vertical = width < 640;
  const ports = { sourcePosition: vertical ? Position.Bottom : Position.Right, targetPosition: vertical ? Position.Top : Position.Left };
  const verdictOf = (id: string) => verdicts?.find((verdict) => verdict.id === id);
  const nodes: Node[] = [
    { id: 'event', position: positions.event, data: { label: eventLabel }, draggable: false, ...ports,
      style: { ...CARD, border: '2px solid hsl(var(--primary))', fontWeight: 700, fontSize: 13 } },
    ...factors.filter((factor) => positions[factor.id]).map((factor) => {
      const verdict = verdictOf(factor.id);
      const tone = verdict ? (verdict.correct ? TONES.ok : TONES.bad) : undefined;
      return { id: factor.id, position: positions[factor.id], data: { label: factor.label }, draggable: false, ...ports,
        style: { ...CARD, ...(tone ? { borderColor: tone, borderWidth: 2 } : {}) } } as Node;
    }),
  ];
  const edges: Edge[] = factors.filter((factor) => positions[factor.id]).map((factor) => {
    const role = chosen[factor.id];
    const verdict = verdictOf(factor.id);
    const color = verdict ? (verdict.correct ? TONES.ok : TONES.bad) : role === 'trigger' ? TONES.trigger : TONES.idle;
    const outgoing = role === 'consequence';
    return {
      id: `${factor.id}-edge`, source: outgoing ? 'event' : factor.id, target: outgoing ? factor.id : 'event',
      type: 'smoothstep', label: role === 'trigger' ? 'повод' : undefined, animated: !verdict,
      style: { stroke: color, strokeWidth: 2, ...(role === 'trigger' ? { strokeDasharray: '6 4' } : {}) },
      markerEnd: { type: MarkerType.ArrowClosed, color, width: 18, height: 18 },
    };
  });
  const layoutKey = nodes.map((node) => `${node.id}:${node.position.x}:${node.position.y}`).join('|');
  // Подгонка и при смене ширины: на телефоне первая подгонка идёт до замера экрана, узел события
  // стоит на том же месте, и без повторной подгонки остаётся за краем пустой рамки.
  useEffect(() => {
    const frame = requestAnimationFrame(() => { void fitView({ padding: 0.15, maxZoom: 1.1 }); });
    return () => cancelAnimationFrame(frame);
  }, [layoutKey, width, height, fitView]);
  return (
    <div ref={box} className="overflow-hidden rounded-xl border border-border bg-background" style={{ height: vertical ? height : Math.min(height, 520) }}
      role="img" aria-label="Схема: причины и повод ведут к событию, событие ведёт к последствиям. Роли выбираются в списке ниже.">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
        nodesFocusable={false} edgesFocusable={false}
        panOnDrag={false} zoomOnScroll={false} zoomOnPinch={false} zoomOnDoubleClick={false} preventScrolling={false}
        proOptions={{ hideAttribution: true }} />
    </div>
  );
}

/**
 * «Причины и следствия»: у каждого фактора ученик выбирает роль — причина, повод, последствие
 * или не связано; схема (React Flow) сразу достраивает стрелки к событию и от него.
 * Главное — отличить причину от повода (Seixas, историческое мышление).
 */
export default function CauseEffectMap(props: CauseEffectMapProps) {
  return <ReactFlowProvider><CauseEffectBoard {...props} /></ReactFlowProvider>;
}

function CauseEffectBoard({ title, instruction, event, factors: raw, explanation, onAnswer }: CauseEffectMapProps) {
  const factors = useMemo(() => normalizeFactors(raw), [raw]);
  const eventLabel = typeof event === 'string' ? event : `${event?.label ?? ''}${event?.year ? ` (${event.year})` : ''}`;
  const [chosen, setChosen] = useState<Record<string, CauseRole | undefined>>({});
  const [verdicts, setVerdicts] = useState<CauseVerdict[] | null>(null);
  const [result, setResult] = useState<BlockResult>('idle');
  const [skipped, setSkipped] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);
  const checked = verdicts !== null;
  const allChosen = factors.every((factor) => chosen[factor.id]);

  if (factors.length < 2 || !eventLabel.trim()) {
    return (
      <BlockShell title={title || 'Причины и следствия'} subtitle={instruction}>
        <p role="alert" className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Задание повреждено: не хватает события или факторов. Сообщите учителю — а урок можно продолжать.
        </p>
        {/* Не засчитываем как верное: повреждённое задание не должно давать «освоено». */}
        {!skipped && <div className="mt-4"><PrimaryAction onClick={() => { setSkipped(true); onAnswer?.(false); }}>Продолжить урок</PrimaryAction></div>}
      </BlockShell>
    );
  }

  const check = () => {
    const next = checkFactors(factors, chosen);
    const score = causeScore(next);
    setVerdicts(next);
    setResult(resultFromScore(score));
    requestAnimationFrame(() => resultRef.current?.focus());
    onAnswer?.(score >= PASS_SCORE);
  };

  return (
    <BlockShell title={title} subtitle={instruction}>
      <Diagram eventLabel={eventLabel} factors={factors} chosen={chosen} verdicts={verdicts} />
      <ul className="mt-4 space-y-2" aria-label="Факторы: выберите роль каждого">
        {(verdicts ?? factors).map((factor) => {
          const verdict = verdicts?.find((item) => item.id === factor.id);
          return (
            <li key={factor.id} className={`rounded-lg border p-3 text-sm ${
              verdict ? (verdict.correct ? 'border-emerald-300 bg-emerald-50' : 'border-destructive/30 bg-destructive/5') : 'border-border'}`}>
              <div className="flex flex-wrap items-center gap-2">
                {verdict && (verdict.correct
                  ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
                  : <XCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />)}
                <span className="min-w-0 flex-1 basis-[calc(100%-2rem)] font-medium sm:basis-auto"><RichText text={factor.label} inline /></span>
                <div role="group" aria-label={`Роль: ${factor.label}`} className="flex flex-wrap gap-1">
                  {CAUSE_ROLES.map((role) => {
                    const active = chosen[factor.id] === role;
                    return (
                      <button key={role} type="button" aria-pressed={active} disabled={checked}
                        onClick={() => setChosen((prev) => ({ ...prev, [factor.id]: role }))}
                        className={`min-h-[44px] rounded-full border px-3 text-xs font-semibold transition-colors disabled:cursor-default ${
                          active ? 'border-primary bg-primary text-primary-foreground' : 'border-border hover:bg-muted'}`}>
                        {ROLE_LABELS[role]}
                      </button>
                    );
                  })}
                </div>
              </div>
              {verdict && (
                <p className="mt-2 text-xs text-muted-foreground">
                  {!verdict.correct && <span className="font-semibold text-destructive">Верно: {ROLE_LABELS[verdict.role]}. </span>}
                  {verdict.kind && KIND_LABELS[verdict.kind] && <span>Вид: {KIND_LABELS[verdict.kind]}. </span>}
                  {verdict.term && <span>{verdict.term === 'long' ? 'Долгосрочное.' : 'Ближайшее.'} </span>}
                  {verdict.explanation && <RichText text={verdict.explanation} inline />}
                </p>
              )}
            </li>
          );
        })}
      </ul>
      {!checked && (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <PrimaryAction onClick={check} disabled={!allChosen}>Проверить схему</PrimaryAction>
          {!allChosen && <span className="text-xs text-muted-foreground">Выберите роль у каждого фактора.</span>}
        </div>
      )}
      <div ref={resultRef} tabIndex={-1} className="outline-none">
        <ResultPanel result={result}
          correctText={explanation || 'Верно: причины, повод и последствия определены.'}
          partialText={explanation ? `Часть ролей определена неверно. ${explanation}` : 'Часть ролей определена неверно — посмотри разбор выше.'}
          incorrectText={explanation ? `Пока неверно. ${explanation}` : 'Пока неверно — посмотри разбор выше.'} />
      </div>
    </BlockShell>
  );
}
