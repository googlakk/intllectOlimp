import { useEffect, useMemo, useRef, useState } from 'react';
import * as visTimeline from 'vis-timeline/standalone';
import type { TimelineOptions } from 'vis-timeline/standalone';
import 'vis-timeline/styles/vis-timeline-graph2d.min.css';
import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { resultFromScore, type BlockResult } from '@/features/interactiveEngines/scoring';
import {
  checkChronology, chronologyRange, chronologyScore, clampYear, defaultTolerance, deltaLabel, initialPlacement, normalizeEvents,
  parseYear, yearLabel, type ChronologyVerdict,
} from '@/features/interactiveEngines/chronology';

export interface ChronologyLineProps {
  title: string;
  instruction: string;
  events: unknown;
  lanes?: Array<{ id: string; label: string }>;
  tolerance_years?: number;
  explanation?: string;
  onAnswer?: (isCorrect: boolean) => void;
}

const PASS_SCORE = 80;
const MIN_EVENTS = 2;

// DataSet есть в сборке standalone, но не в её объявлениях типов.
type VisDataSet = { update(items: unknown): void };
const { Timeline } = visTimeline;
const DataSet = (visTimeline as unknown as { DataSet: new (items?: unknown[]) => VisDataSet }).DataSet;

function toDate(year: number): Date {
  const date = new Date(2000, 0, 1);
  date.setFullYear(year);
  return date;
}

function toYear(date: Date | number | string): number {
  const value = new Date(date);
  return value.getMonth() >= 6 ? value.getFullYear() + 1 : value.getFullYear();
}

function itemFor(event: { id: string; label: string; lane?: string }, year: number, hasLanes: boolean, verdict?: ChronologyVerdict) {
  return {
    id: event.id, content: event.label, start: toDate(year), type: 'box',
    className: verdict ? `chronology-item ${verdict.correct ? 'chronology-ok' : 'chronology-miss'}` : 'chronology-item',
    ...(verdict ? { editable: false, title: yearLabel(verdict.year) } : {}),
    ...(hasLanes ? { group: event.lane } : {}),
  };
}

/**
 * «Лента событий»: карточки разложены по ленте вперемешку — ученик перетаскивает их на свои годы
 * (мышью или пальцем; год можно ввести и в списке под лентой). Проверка ставит каждую на место
 * и показывает, на сколько лет ошибся. Лента — vis-timeline (MIT/Apache-2.0).
 */
export default function ChronologyLine({ title, instruction, events, lanes, tolerance_years, explanation, onAnswer }: ChronologyLineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);
  const itemsRef = useRef<VisDataSet | null>(null);
  const timelineRef = useRef<InstanceType<typeof Timeline> | null>(null);
  const valid = useMemo(() => normalizeEvents(events), [events]);
  const idsKey = valid.map((event) => `${event.id}:${event.year}`).join('|');
  const range = useMemo(() => (valid.length ? chronologyRange(valid) : { from: 0, to: 1 }), [valid]);
  const [placed, setPlaced] = useState<Record<string, number>>(() => initialPlacement(valid));
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [verdicts, setVerdicts] = useState<ChronologyVerdict[] | null>(null);
  const [result, setResult] = useState<BlockResult>('idle');
  const [skipped, setSkipped] = useState(false);
  const tolerance = tolerance_years && tolerance_years > 0 ? tolerance_years : defaultTolerance(valid);
  const checked = verdicts !== null;
  const hasLanes = Boolean(lanes && lanes.length > 1);
  // Лента читает текущую расстановку и результат через ref: пересоздание ленты не сбрасывает работу ученика.
  const stateRef = useRef({ placed, verdicts });
  stateRef.current = { placed, verdicts };

  // Другие события (другой урок) — новая стартовая раскладка.
  const firstKey = useRef(idsKey);
  useEffect(() => {
    if (firstKey.current === idsKey) return;
    firstKey.current = idsKey;
    setPlaced(initialPlacement(valid));
    setDrafts({});
    setVerdicts(null);
    setResult('idle');
  }, [idsKey]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!containerRef.current || valid.length < MIN_EVENTS) return;
    const { placed: current, verdicts: done } = stateRef.current;
    const fallback = initialPlacement(valid);
    const items = new DataSet(valid.map((event) => {
      const verdict = done?.find((item) => item.id === event.id);
      return itemFor(event, verdict ? verdict.year : current[event.id] ?? fallback[event.id], hasLanes, verdict);
    }));
    itemsRef.current = items;
    const options: TimelineOptions = {
      editable: done ? false : { updateTime: true, updateGroup: false, add: false, remove: false, overrideItems: false },
      snap: (date: Date) => toDate(toYear(date)),
      min: toDate(range.from), max: toDate(range.to), start: toDate(range.from), end: toDate(range.to),
      zoomMin: 1000 * 60 * 60 * 24 * 365 * 5,
      showCurrentTime: false, orientation: 'top', stack: true, zoomKey: 'ctrlKey',
      margin: { item: { horizontal: 4, vertical: 8 } },
      // Годы до н. э. — подписью, а не «-0500».
      format: {
        minorLabels: (date: Date) => { const year = toYear(date); return year < 0 ? `${-year} до н. э.` : String(year); },
        majorLabels: () => '',
      } as unknown as TimelineOptions['format'],
      tooltipOnItemUpdateTime: { template: (item: { start: Date }) => yearLabel(toYear(item.start)) },
      onMove: (item, callback) => {
        setPlaced((prev) => ({ ...prev, [String(item.id)]: toYear(item.start as Date) }));
        setDrafts((prev) => { const next = { ...prev }; delete next[String(item.id)]; return next; });
        callback(item);
      },
    };
    const timeline = hasLanes
      ? new Timeline(containerRef.current, items as never, new DataSet((lanes || []).map((lane) => ({ id: lane.id, content: lane.label }))) as never, options)
      : new Timeline(containerRef.current, items as never, options);
    timelineRef.current = timeline;
    // Урок масштабируется под экран — ленту перерисовываем по фактическому размеру.
    let frame = 0;
    const observer = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => timeline.redraw());
    });
    observer.observe(containerRef.current);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      timeline.destroy();
      timelineRef.current = null;
      itemsRef.current = null;
    };
  }, [valid, hasLanes, lanes, range]);

  // Год из списка применяется по Enter или при уходе из поля — не на каждой цифре.
  const commitYear = (id: string) => {
    const draft = drafts[id];
    if (checked || draft === undefined) return;
    const parsed = parseYear(draft);
    setDrafts((prev) => { const next = { ...prev }; delete next[id]; return next; });
    if (parsed === null) return;
    const year = clampYear(parsed, range);
    setPlaced((prev) => ({ ...prev, [id]: year }));
    itemsRef.current?.update({ id, start: toDate(year) });
  };

  const check = () => {
    const next = checkChronology(valid, placed, tolerance);
    const score = chronologyScore(next);
    setVerdicts(next);
    setResult(resultFromScore(score));
    // После проверки каждая карточка встаёт на свой год: верные — зелёные, ошибочные — красные.
    itemsRef.current?.update(next.map((verdict) => itemFor(valid.find((event) => event.id === verdict.id)!, verdict.year, hasLanes, verdict)));
    timelineRef.current?.setOptions({ editable: false });
    requestAnimationFrame(() => {
      timelineRef.current?.fit({ animation: false });
      resultRef.current?.focus();
    });
    onAnswer?.(score >= PASS_SCORE);
  };

  if (valid.length < MIN_EVENTS) {
    // Повреждённое задание не должно запирать урок: ученик может пройти дальше.
    return (
      <BlockShell title={title || 'Лента событий'} subtitle={instruction}>
        <p role="alert" className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          Задание повреждено: в нём не хватает событий с годами. Сообщите учителю — а урок можно продолжать.
        </p>
        {!skipped && <div className="mt-4"><PrimaryAction onClick={() => { setSkipped(true); onAnswer?.(true); }}>Продолжить урок</PrimaryAction></div>}
      </BlockShell>
    );
  }

  const ordered = checked ? [...valid].sort((a, b) => a.year - b.year) : [...valid].sort((a, b) => (placed[a.id] ?? 0) - (placed[b.id] ?? 0));

  return (
    <BlockShell title={title} subtitle={instruction}>
      <div className="chronology-line rounded-lg border border-border bg-background" ref={containerRef} role="group"
        aria-label="Лента времени. Годы можно также ввести в списке событий ниже." />
      <p className="mt-2 text-xs text-muted-foreground">
        Перетаскивайте карточки по ленте{hasLanes ? ' в своей строке' : ''} или введите год в списке. Масштаб — колесо мыши с Ctrl.
      </p>

      <ol className="mt-4 space-y-2" aria-label="События и годы">
        {ordered.map((event) => {
          const verdict = verdicts?.find((item) => item.id === event.id);
          return (
            <li key={event.id} className={`flex flex-wrap items-center gap-3 rounded-lg border p-3 text-sm ${
              verdict ? (verdict.correct ? 'border-emerald-300 bg-emerald-50' : 'border-destructive/30 bg-destructive/5') : 'border-border'}`}>
              {verdict && (verdict.correct
                ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
                : <XCircle className="h-4 w-4 shrink-0 text-destructive" aria-hidden />)}
              <span className="min-w-0 flex-1 font-medium"><RichText text={event.label} inline /></span>
              {verdict ? (
                <span className="text-xs">
                  <strong>{yearLabel(verdict.year)}</strong>
                  {!verdict.correct && <span className="text-destructive"> · ты поставил {yearLabel(verdict.placed)} — {deltaLabel(verdict.delta)}</span>}
                </span>
              ) : (
                <label className="flex items-center gap-2 text-xs text-muted-foreground">
                  год
                  <input type="text" inputMode="numeric" value={drafts[event.id] ?? String(placed[event.id] ?? '')}
                    onChange={(changeEvent) => setDrafts((prev) => ({ ...prev, [event.id]: changeEvent.target.value }))}
                    onBlur={() => commitYear(event.id)}
                    onKeyDown={(keyEvent) => { if (keyEvent.key === 'Enter') commitYear(event.id); }}
                    className="h-9 w-24 rounded-md border border-border bg-background px-2 text-sm text-foreground"
                    aria-label={`Год события: ${event.label}`} />
                </label>
              )}
              {verdict?.explanation && <p className="basis-full text-xs text-muted-foreground"><RichText text={verdict.explanation} inline /></p>}
            </li>
          );
        })}
      </ol>

      {!checked && <div className="mt-4"><PrimaryAction onClick={check}>Проверить ленту</PrimaryAction></div>}
      <div ref={resultRef} tabIndex={-1} className="outline-none">
        <ResultPanel result={result}
          correctText={explanation || 'Верно: события стоят на своих местах.'}
          partialText={explanation ? `Часть событий стоит не там. ${explanation}` : 'Часть событий стоит не там — посмотри разбор выше.'}
          incorrectText={explanation ? `Пока неверно. ${explanation}` : 'Пока неверно — посмотри разбор выше.'} />
      </div>
      <style>{`
        .chronology-line .vis-timeline { border: 0; font-family: inherit; }
        .chronology-line .vis-item.chronology-item { border-radius: 10px; border-color: hsl(var(--primary) / 0.5);
          background: hsl(var(--card)); color: hsl(var(--foreground)); font-size: 12px; max-width: 220px; white-space: normal; }
        .chronology-line .vis-item.chronology-item.vis-selected { border-color: hsl(var(--primary)); box-shadow: 0 0 0 2px hsl(var(--primary) / 0.25); }
        .chronology-line .vis-item.chronology-ok { border-color: rgb(16 185 129); background: rgb(236 253 245); }
        .chronology-line .vis-item.chronology-miss { border-color: hsl(var(--destructive)); background: hsl(var(--destructive) / 0.08); }
        .chronology-line .vis-time-axis .vis-text { color: hsl(var(--muted-foreground)); }
      `}</style>
    </BlockShell>
  );
}
