import { useEffect, useId, useMemo, useRef, useState } from 'react';
import katex from 'katex';
import { CheckCircle2, Eye, Target, XCircle } from 'lucide-react';
import { BlockShell } from './shared';
import { RichText } from './RichText';
import { mathToLatex } from '@/features/interactiveEngines/mathExpression';
import {
  normalizeExplorer, reachedTarget, sampleCurve, substituteParams, type ExplorerPoint,
} from '@/features/interactiveEngines/functionExplorer';

export interface FunctionExplorerProps {
  title?: string;
  instruction?: string;
  formula: string;
  params?: unknown;
  x_range?: unknown;
  y_range?: unknown;
  target?: unknown;
  points?: unknown;
  prediction?: unknown;
  explanation?: string;
  onAnswer?: (isCorrect: boolean) => void;
}

const PAD = 24;
// Столько движений ползунков без совпадения — и можно открыть ответ, чтобы урок не застрял.
const REVEAL_AFTER_MOVES = 12;

function Formula({ latex }: { latex: string }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(latex, { throwOnError: false });
    } catch {
      return null;
    }
  }, [latex]);
  return html ? <span dangerouslySetInnerHTML={{ __html: html }} /> : null;
}

/** Координатная плоскость как в тетради: оси через ноль, клетка, подписи через единицу или две. */
function Plane({ xRange, yRange, curves, points }: {
  xRange: [number, number]; yRange: [number, number];
  curves: { segments: ExplorerPoint[][]; tone: 'main' | 'target' }[]; points: ExplorerPoint[];
}) {
  // Рисуем в настоящих пикселях: на телефоне подписи осей остаются читаемыми, а не уменьшаются вместе с картинкой.
  const clipId = `plane-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const box = useRef<HTMLDivElement>(null);
  const [WIDTH, setWidth] = useState(480);
  useEffect(() => {
    if (!box.current) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(260, Math.round(entry.contentRect.width))));
    observer.observe(box.current);
    return () => observer.disconnect();
  }, []);
  const HEIGHT = Math.round(Math.min(380, WIDTH * 0.8));
  const sx = (x: number) => PAD + ((x - xRange[0]) / (xRange[1] - xRange[0])) * (WIDTH - 2 * PAD);
  const sy = (y: number) => HEIGHT - PAD - ((y - yRange[0]) / (yRange[1] - yRange[0])) * (HEIGHT - 2 * PAD);
  const clampY = (y: number) => Math.max(yRange[0] - 1, Math.min(yRange[1] + 1, y));
  // На узком экране подписи через одну, чтобы не слипались.
  const every = (xRange[1] - xRange[0]) / WIDTH > 0.03 ? 2 : 1;
  const xs = [];
  for (let x = Math.ceil(xRange[0]); x <= xRange[1]; x += 1) xs.push(x);
  const ys = [];
  for (let y = Math.ceil(yRange[0]); y <= yRange[1]; y += 1) ys.push(y);
  const x0 = sx(Math.min(Math.max(0, xRange[0]), xRange[1]));
  const y0 = sy(Math.min(Math.max(0, yRange[0]), yRange[1]));
  return (
    <div ref={box} className="w-full">
    <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`} className="block max-w-full rounded-lg border bg-background" role="img" aria-label="График функции">
      <defs>
        <clipPath id={clipId}><rect x={PAD} y={PAD} width={WIDTH - 2 * PAD} height={HEIGHT - 2 * PAD} /></clipPath>
      </defs>
      {xs.map((x) => <line key={`gx${x}`} x1={sx(x)} x2={sx(x)} y1={PAD} y2={HEIGHT - PAD} className="stroke-border" strokeWidth={0.6} />)}
      {ys.map((y) => <line key={`gy${y}`} y1={sy(y)} y2={sy(y)} x1={PAD} x2={WIDTH - PAD} className="stroke-border" strokeWidth={0.6} />)}
      <line x1={PAD} x2={WIDTH - PAD + 8} y1={y0} y2={y0} className="stroke-foreground" strokeWidth={1.2} markerEnd="" />
      <line y1={HEIGHT - PAD} y2={PAD - 8} x1={x0} x2={x0} className="stroke-foreground" strokeWidth={1.2} />
      <text x={WIDTH - PAD + 4} y={y0 - 6} className="fill-foreground text-[12px] italic">x</text>
      <text x={x0 + 6} y={PAD - 6} className="fill-foreground text-[12px] italic">y</text>
      {xs.filter((x) => x !== 0 && x % every === 0).map((x) => (
        <text key={`lx${x}`} x={sx(x)} y={y0 + 13} textAnchor="middle" className="fill-muted-foreground text-[10px]">{x}</text>
      ))}
      {ys.filter((y) => y !== 0 && y % every === 0).map((y) => (
        <text key={`ly${y}`} x={x0 - 5} y={sy(y) + 3} textAnchor="end" className="fill-muted-foreground text-[10px]">{y}</text>
      ))}
      <text x={x0 - 5} y={y0 + 13} textAnchor="end" className="fill-muted-foreground text-[10px]">0</text>
      <g clipPath={`url(#${clipId})`}>
        {curves.map((curve, index) => curve.segments.map((segment, part) => (
          <polyline
            key={`${index}-${part}`}
            points={segment.map((point) => `${sx(point.x)},${sy(clampY(point.y))}`).join(' ')}
            fill="none"
            stroke={curve.tone === 'target' ? 'hsl(var(--muted-foreground))' : 'hsl(var(--primary))'}
            strokeWidth={curve.tone === 'target' ? 2 : 2.5}
            strokeDasharray={curve.tone === 'target' ? '6 5' : undefined}
            strokeLinejoin="round"
          />
        )))}
        {points.map((point, index) => (
          <g key={index}>
            <circle cx={sx(point.x)} cy={sy(point.y)} r={4} className="fill-amber-500" />
            {point.label && <text x={sx(point.x) + 7} y={sy(point.y) - 7} className="fill-foreground text-[11px] font-medium">{point.label}</text>}
          </g>
        ))}
      </g>
    </svg>
    </div>
  );
}

export default function FunctionExplorer({ title, instruction, formula, params, x_range, y_range, target, points, prediction, explanation, onAnswer }: FunctionExplorerProps) {
  const explorer = useMemo(
    () => normalizeExplorer({ formula, params, x_range, y_range, target, points, prediction }),
    [formula, params, x_range, y_range, target, points, prediction],
  );
  const [values, setValues] = useState<Record<string, number>>(
    () => Object.fromEntries((explorer?.params ?? []).map((param) => [param.name, param.initial])),
  );
  const [choice, setChoice] = useState<string | null>(null);
  const [finished, setFinished] = useState(false);
  // Цель засчитывается только после движения ползунка; «Показать ответ» — после нескольких попыток.
  const [moves, setMoves] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const reported = useRef(false);
  const idPrefix = `fx-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;

  const predicted = !explorer?.prediction || choice !== null;
  const predictionRight = !explorer?.prediction || choice === explorer.prediction.correctAnswer;
  const onTarget = explorer ? moves > 0 && reachedTarget(values, explorer.target, explorer.params) : false;

  // Задание засчитывается один раз: прогноз сделан и (если есть цель) график совпал с пунктиром.
  useEffect(() => {
    if (!explorer || reported.current || !predicted || (explorer.target && !onTarget)) return;
    if (!explorer.target && !explorer.prediction) return;
    reported.current = true;
    setFinished(true);
    // Засчитывается прогноз; цель с подсказкой «Показать ответ» — уже не самостоятельное решение.
    onAnswer?.(predictionRight && !revealed);
  }, [explorer, predicted, onTarget, predictionRight, revealed, onAnswer]);

  if (!explorer) {
    return <BlockShell title={title || 'График по формуле'}><p className="text-sm text-muted-foreground">Задание собрано с ошибкой — сообщите учителю.</p></BlockShell>;
  }

  const decimals = (step: number) => (String(step).split('.')[1] ?? '').length;
  const shown = (value: number) => String(value).replace('.', ',');
  const setParam = (name: string, raw: number, step: number) => {
    // Округляем до знаков шага: 0,1 + 0,2 не превращается в 0,30000000000000004.
    const value = Number(raw.toFixed(decimals(step)));
    setValues((current) => ({ ...current, [name]: value }));
    setMoves((count) => count + 1);
  };
  const reveal = () => {
    if (!explorer?.target) return;
    setRevealed(true);
    setValues({ ...explorer.target });
    setMoves((count) => count + 1);
  };
  const currentLatex = `y = ${mathToLatex(substituteParams(explorer.formula, values))}`;
  const targetLatex = explorer.target ? `y = ${mathToLatex(substituteParams(explorer.formula, explorer.target))}` : null;

  const curves = [
    ...(explorer.target ? [{ segments: sampleCurve(explorer.formula, explorer.target, explorer.xRange, explorer.yRange), tone: 'target' as const }] : []),
    ...(predicted ? [{ segments: sampleCurve(explorer.formula, values, explorer.xRange, explorer.yRange), tone: 'main' as const }] : []),
  ];

  return (
    <BlockShell title={title || 'График по формуле'} subtitle={instruction}>
      <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-lg">
        <Formula latex={`y = ${mathToLatex(explorer.formula)}`} />
        {explorer.params.length > 0 && predicted && (
          <span className="text-base text-muted-foreground">сейчас: <Formula latex={currentLatex} /></span>
        )}
      </div>

      {explorer.prediction && choice === null && (
        <div className="mb-4 rounded-lg border bg-primary/5 p-4">
          <p className="mb-3 text-sm font-semibold">Сначала предскажи: <RichText text={explorer.prediction.question} inline /></p>
          <div className="grid gap-2 sm:grid-cols-2">
            {explorer.prediction.options.map((option) => (
              <button key={option} type="button" onClick={() => setChoice(option)}
                className="rounded-lg border bg-background p-3 text-left text-sm hover:border-primary/50 hover:bg-primary/5">
                <RichText text={option} inline />
              </button>
            ))}
          </div>
        </div>
      )}

      {explorer.prediction && choice !== null && (
        <div role="status" className={`mb-4 flex items-start gap-2 rounded-lg border p-3 text-sm ${predictionRight ? 'border-green-500/20 bg-green-500/10 text-green-800 dark:text-green-300' : 'border-amber-500/30 bg-amber-500/10 text-amber-800 dark:text-amber-200'}`}>
          {predictionRight ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" /> : <XCircle className="mt-0.5 h-4 w-4 shrink-0" />}
          <span>
            {predictionRight ? 'Прогноз верный. ' : `Прогноз не подтвердился — верно: «${explorer.prediction.correctAnswer}». `}
            {explorer.prediction.explanation && <RichText text={explorer.prediction.explanation} inline />} Подвигай ползунки и проверь сам.
          </span>
        </div>
      )}

      {/* Для экранного диктора: что нарисовано и совпало ли с целью. */}
      <p className="sr-only" role="status">
        {predicted ? `Сейчас график ${currentLatex}.` : ''} {targetLatex ? `Цель: ${targetLatex}. ${onTarget ? 'График совпал с целью.' : 'Пока не совпадает.'}` : ''}
      </p>
      <Plane xRange={explorer.xRange} yRange={explorer.yRange} curves={curves} points={explorer.points} />

      {predicted && explorer.params.length > 0 && (
        <div className="mt-4 space-y-4 rounded-lg border bg-muted/20 p-4">
          {explorer.params.map((param) => (
            <div key={param.name}>
              <div className="mb-1 flex items-center justify-between text-sm">
                <label htmlFor={`${idPrefix}-${param.name}`} className="font-medium"><RichText text={param.label || param.name} inline /></label>
                <span className="rounded bg-primary/10 px-2 py-0.5 font-mono text-primary">{shown(values[param.name])}</span>
              </div>
              <input
                id={`${idPrefix}-${param.name}`}
                data-param={param.name}
                aria-valuetext={`${param.name} равно ${shown(values[param.name])}`}
                type="range"
                min={param.min}
                max={param.max}
                step={param.step}
                value={values[param.name]}
                disabled={finished && Boolean(explorer.target)}
                onChange={(event) => setParam(param.name, Number(event.target.value), param.step)}
                className="w-full accent-primary"
              />
            </div>
          ))}
        </div>
      )}

      {explorer.target && predicted && !onTarget && (
        <p className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
          <Target className="h-4 w-4 shrink-0" /> Подбери значения так, чтобы твой график лёг на пунктирный.
          {moves >= REVEAL_AFTER_MOVES && (
            <button type="button" onClick={reveal} className="ml-auto inline-flex items-center gap-1.5 font-medium text-muted-foreground hover:text-foreground">
              <Eye className="h-4 w-4" /> Показать ответ
            </button>
          )}
        </p>
      )}

      {finished && (
        <div className="mt-4 space-y-3">
          {explorer.target && (
            <div className="flex items-center gap-2 rounded-lg border border-green-500/20 bg-green-500/10 p-3.5 text-sm font-medium text-green-700 dark:text-green-400">
              <CheckCircle2 className="h-5 w-5 shrink-0" /> {revealed ? 'Вот нужный график:' : 'Графики совпали:'} <Formula latex={currentLatex} />
            </div>
          )}
          {explanation && <div className="rounded-lg border bg-muted/30 p-4 text-sm"><RichText text={explanation} /></div>}
        </div>
      )}
    </BlockShell>
  );
}
