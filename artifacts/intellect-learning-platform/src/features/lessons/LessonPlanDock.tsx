import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { Check, ChevronDown, Trophy } from 'lucide-react';
import type { Block, LessonDocument } from '@/lib/api/types';
import { isAssessmentBlock } from '@/lib/lessonBlocks';
import { lessonPositionForBlock } from './lessonExperience';
import type { LessonAnswers } from './studentProgress';

type LessonPlanDockProps = {
  activeBlocks: Block[];
  activeOriginalIndices: number[];
  answers: LessonAnswers;
  currentStep: number;
  isCompleted: boolean;
  maxOpenedStep: number;
  lessonDocument?: LessonDocument;
  onNavigate: (index: number) => void;
  onOpenSummary: () => void;
};

const plain = (text: string) => text.replace(/\$/g, '').replace(/[*_`#]/g, '').trim();

/** Кольцо прогресса: сколько шагов урока пройдено. */
function ProgressRing({ value }: { value: number }) {
  const radius = 13;
  const length = 2 * Math.PI * radius;
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8 shrink-0 -rotate-90" aria-hidden>
      <circle cx="16" cy="16" r={radius} fill="none" stroke="currentColor" strokeWidth="3" className="text-white/15" />
      <circle cx="16" cy="16" r={radius} fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"
        className="text-primary transition-[stroke-dashoffset] duration-500"
        strokeDasharray={length} strokeDashoffset={length * (1 - Math.min(1, Math.max(0, value)))} />
    </svg>
  );
}

/**
 * План урока — плашка в правом верхнем углу, как у помощника: свёрнута показывает текущий шаг,
 * при наведении (или нажатии на телефоне) раскрывается в список, прокрученный к текущему шагу.
 */
export function LessonPlanDock({
  activeBlocks, activeOriginalIndices, answers, currentStep, isCompleted, maxOpenedStep, lessonDocument, onNavigate, onOpenSummary,
}: LessonPlanDockProps) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const reduceMotion = useReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLButtonElement>(null);
  const total = activeBlocks.length;
  const onSummary = currentStep >= total;
  const titleFor = (index: number) => {
    const position = lessonPositionForBlock(lessonDocument, activeOriginalIndices[index] ?? index);
    return plain(position?.scene.title || (isAssessmentBlock(activeBlocks[index]) ? 'Практика' : 'Теория'));
  };
  const currentTitle = onSummary ? 'Итоги урока' : titleFor(currentStep);
  const doneCount = activeBlocks.filter((_block, index) =>
    index < maxOpenedStep || answers[activeOriginalIndices[index] ?? index] !== undefined).length;

  // Раскрыли — сразу видно текущий шаг, без прокрутки вручную.
  useEffect(() => {
    if (open) requestAnimationFrame(() => activeRef.current?.scrollIntoView({ block: 'center', behavior: reduceMotion ? 'auto' : 'smooth' }));
  }, [open, currentStep, reduceMotion]);

  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) { setOpen(false); setPinned(false); }
    };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); setPinned(false); } };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  const hover = (event: ReactPointerEvent, entering: boolean) => {
    if (event.pointerType !== 'mouse' || pinned) return;
    setOpen(entering);
  };
  const go = (action: () => void) => { action(); setOpen(false); setPinned(false); };

  return (
    <div ref={rootRef} className="relative h-11 w-[min(300px,calc(100vw-9rem))]"
      onPointerEnter={(event) => hover(event, true)} onPointerLeave={(event) => hover(event, false)}>
      <div className={`absolute right-0 top-0 z-[65] overflow-hidden rounded-[22px] border border-white/10 bg-neutral-900/95 text-white shadow-2xl backdrop-blur-xl transition-[width] duration-300 ease-out motion-reduce:transition-none ${open ? 'w-[min(360px,calc(100vw-1.5rem))]' : 'w-full'}`}>
        <button type="button" aria-expanded={open} aria-label={`План урока: шаг ${Math.min(currentStep + 1, total)} из ${total}, ${currentTitle}`}
          onClick={() => { const next = !pinned; setPinned(next); setOpen(next); }}
          className="flex h-11 w-full items-center gap-2.5 pl-1.5 pr-3 text-left">
          <ProgressRing value={total ? doneCount / total : 0} />
          <span className="min-w-0 flex-1">
            <span className="block text-[10px] font-semibold uppercase tracking-wide text-white/50">
              {onSummary ? 'Урок пройден' : `Шаг ${currentStep + 1} из ${total}`}
            </span>
            <span className="relative block h-4 overflow-hidden text-sm leading-4">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span key={currentTitle} className="absolute inset-0 truncate"
                  initial={reduceMotion ? false : { y: 10, opacity: 0 }} animate={{ y: 0, opacity: 1 }}
                  exit={reduceMotion ? undefined : { y: -10, opacity: 0 }} transition={{ duration: 0.25 }}>
                  {currentTitle}
                </motion.span>
              </AnimatePresence>
            </span>
          </span>
          <ChevronDown className={`h-4 w-4 shrink-0 text-white/60 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
        </button>

        <AnimatePresence initial={false}>
          {open && (
            <motion.nav key="plan" aria-label="План урока"
              initial={reduceMotion ? false : { height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
              exit={reduceMotion ? undefined : { height: 0, opacity: 0 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
              <ol className="max-h-[min(60vh,480px)] space-y-1 overflow-y-auto border-t border-white/10 p-2">
                {activeBlocks.slice(0, maxOpenedStep + 1).map((block, index) => {
                  const originalIndex = activeOriginalIndices[index] ?? index;
                  const position = lessonPositionForBlock(lessonDocument, originalIndex);
                  const previous = lessonPositionForBlock(lessonDocument, index > 0 ? activeOriginalIndices[index - 1] : undefined);
                  const showEpisode = position && position.episode.id !== previous?.episode.id;
                  const active = index === currentStep;
                  const done = index < maxOpenedStep || answers[originalIndex] !== undefined;
                  return (
                    <li key={position?.scene.id || `${block.component}-${index}`}>
                      {showEpisode && <p className="px-2 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-white/45">{plain(position.episode.title)}</p>}
                      <button ref={active ? activeRef : undefined} type="button" aria-current={active ? 'step' : undefined}
                        onClick={() => go(() => onNavigate(index))}
                        className={`flex min-h-[40px] w-full items-center gap-2.5 rounded-xl px-2 py-1.5 text-left text-sm transition-colors ${active ? 'bg-white/15 text-white' : 'text-white/70 hover:bg-white/10 hover:text-white'}`}>
                        <span className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold ${done ? 'bg-primary text-primary-foreground' : active ? 'bg-white text-neutral-900' : 'bg-white/10 text-white/60'}`}>
                          {done ? <Check className="h-3.5 w-3.5" aria-hidden /> : index + 1}
                        </span>
                        <span className="min-w-0 flex-1 truncate">{titleFor(index)}</span>
                      </button>
                    </li>
                  );
                })}
                {isCompleted && (
                  <li>
                    <button ref={onSummary ? activeRef : undefined} type="button" onClick={() => go(onOpenSummary)}
                      className={`mt-1 flex min-h-[40px] w-full items-center gap-2.5 rounded-xl px-2 py-1.5 text-left text-sm ${onSummary ? 'bg-white/15' : 'text-white/70 hover:bg-white/10'}`}>
                      <span className="grid h-6 w-6 place-items-center rounded-full bg-amber-400 text-neutral-900"><Trophy className="h-3.5 w-3.5" aria-hidden /></span>
                      Итоги
                    </button>
                  </li>
                )}
              </ol>
            </motion.nav>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
