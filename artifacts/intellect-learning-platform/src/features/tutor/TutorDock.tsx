import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowLeft, ChevronDown, ChevronRight, EyeOff, Lightbulb, Loader2, Pause, Play, RotateCcw, Send, UserRound, Volume2 } from 'lucide-react';
import type { AvatarCue } from '@/lib/api/types';
import { useAvatarNarration } from '@/features/lessons/useAvatarNarration';
import { parseMathText } from '@/components/blocks/ShortExplanation';
import { tutorTeasers } from './tutorRules';
import type { LessonTutor } from './useLessonTutor';

type DockMode = 'idle' | 'peek' | 'open' | 'speak';

/** Рассказчик урока (аватар): реплика сценария на текущем шаге. */
export type CompanionInput = {
  cue?: AvatarCue;
  previewImageUrl?: string | null;
  name?: string;
  lessonVersionId?: number | null;
  avatarEnabled: boolean;
  audioEnabled: boolean;
  onAvatarEnabledChange: (enabled: boolean) => void;
  onAudioEnabledChange: (enabled: boolean) => void;
};

const EMPTY: never[] = [];
// Реплика аватара сама сворачивается: не мешает, если ученик её не слушает.
// На телефоне она выезжает над строкой с «Продолжить», чтобы кнопку не закрывать.
const SPEAK_IDLE_MS = 9000;
const SPEAK_DONE_MS = 2500;

const STUCK_MESSAGE = 'Не понимаю, что делать';
const TEASER_MS = 5000;
// Ширина плашки по состояниям: в покое — компактная, при наведении шире, в разговоре — окно чата.
// Не шире своего места в строке: иначе закроет кнопку «Продолжить».
const WIDTH: Record<DockMode, string> = {
  idle: 'w-full lg:w-[min(340px,100%)]',
  peek: 'w-full lg:w-[min(560px,100%)]',
  // На телефоне чат во всю ширину экрана, а не только своей части строки.
  open: 'w-[calc(100vw-2rem)] lg:w-[min(680px,100%)]',
  speak: 'w-[calc(100vw-2rem)] lg:w-[min(520px,100%)]',
};

/** «Живой» значок помощника: мягко дышит, при предложении помощи — светится. */
function TutorOrb({ calling, imageUrl, narrator = false, speaking = false }: {
  calling: boolean; imageUrl?: string | null; narrator?: boolean; speaking?: boolean;
}) {
  const reduceMotion = useReducedMotion();
  if (imageUrl || narrator) {
    // Лицо рассказчика вместо шарика: говорит — вокруг пульсирует кольцо.
    return (
      <span className="relative grid h-9 w-9 shrink-0 place-items-center" aria-hidden>
        {(calling || speaking) && !reduceMotion && (
          <motion.span className="absolute inset-0 rounded-full bg-primary/50"
            animate={{ scale: [1, 1.45], opacity: [0.6, 0] }} transition={{ duration: 1.4, repeat: Infinity, ease: 'easeOut' }} />
        )}
        {imageUrl
          ? <img src={imageUrl} alt="" className="relative h-8 w-8 rounded-full object-cover object-top ring-2 ring-primary/70" />
          // Картинка аватара не настроена — силуэт рассказчика, чтобы было видно, что это персонаж.
          : <span className="relative grid h-8 w-8 place-items-center rounded-full bg-primary text-white ring-2 ring-primary/40"><UserRound className="h-5 w-5" /></span>}
      </span>
    );
  }
  return (
    <span className="relative grid h-8 w-8 shrink-0 place-items-center" aria-hidden>
      {calling && !reduceMotion && (
        <motion.span
          className="absolute inset-0 rounded-full bg-primary/50"
          animate={{ scale: [1, 1.7], opacity: [0.6, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
        />
      )}
      <motion.span
        className="h-6 w-6 rounded-full bg-gradient-to-br from-primary via-violet-400 to-sky-300 shadow-[0_0_14px_rgba(124,92,255,0.55)]"
        animate={reduceMotion ? undefined : { scale: [1, 1.1, 1], rotate: [0, 12, 0] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: 'easeInOut' }}
      />
    </span>
  );
}

/**
 * Помощник урока — плашка внизу, как у ассистентов в приложениях:
 * в покое показывает короткие реплики, при наведении расширяется, в разговоре раскрывается в чат.
 */
export function TutorDock({ tutor, companion }: { tutor?: LessonTutor; companion?: CompanionInput }) {
  const [mode, setMode] = useState<DockMode>('idle');
  const [draft, setDraft] = useState('');
  const [teaserIndex, setTeaserIndex] = useState(0);
  const [announcement, setAnnouncement] = useState('');
  const reduceMotion = useReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const idleRef = useRef<HTMLButtonElement>(null);
  const collapseRef = useRef<HTMLButtonElement>(null);
  const chatId = useId();
  const endRef = useRef<HTMLDivElement>(null);
  const announced = useRef(new Set<string>());
  const locked = tutor?.locked ?? false;
  const pending = tutor?.pending ?? false;
  const messages = tutor?.messages ?? EMPTY;
  const hasOffer = tutor?.hasOffer ?? false;
  const seenOffer = tutor?.seenOffer;
  const open = mode === 'open';
  const speaking = mode === 'speak';
  const hovered = useRef(false);
  const narration = useAvatarNarration({
    cue: companion?.cue, lessonVersionId: companion?.lessonVersionId,
    avatarEnabled: companion?.avatarEnabled ?? false, audioEnabled: companion?.audioEnabled ?? false,
    onAudioEnabledChange: companion?.onAudioEnabledChange ?? (() => undefined),
  });
  const cueText = companion?.avatarEnabled ? narration.narration : '';
  const faceUrl = companion?.avatarEnabled ? companion?.previewImageUrl : null;
  const narrator = Boolean(cueText);
  const lastReply = useMemo(() => messages.filter((message) => message.role === 'tutor').at(-1), [messages]);
  const teasers = tutor
    ? tutorTeasers({ locked, hasOffer, lastReply: lastReply?.text })
    : [cueText ? `${companion?.name || 'Рассказчик'}: нажми, чтобы послушать` : 'Рассказчик урока'];
  const teaser = teasers[teaserIndex % teasers.length];

  // Новый шаг со своей репликой — рассказчик выходит сказать её, потом сам сворачивается.
  const cueKey = `${companion?.cue?.id ?? ''}:${companion?.cue?.beat_id ?? ''}`;
  // Сама выезжает один раз на реплику: при возврате на шаг — только по нажатию.
  const shownCues = useRef(new Set<string>());
  useEffect(() => {
    const firstTime = Boolean(cueText) && !shownCues.current.has(cueKey);
    if (firstTime) shownCues.current.add(cueKey);
    // На шаге без реплики плашка возвращается в обычный вид.
    setMode((current) => (current === 'open' ? current : firstTime ? 'speak' : current === 'speak' ? 'idle' : current));
  }, [cueKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Ушли из реплики (открыли чат, сменился шаг) — озвучку на паузу: иначе она звучит без кнопок.
  useEffect(() => {
    if (mode !== 'speak' && (narration.state === 'speaking' || narration.loading)) narration.pause();
  }, [mode, narration.state, narration.loading]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!speaking || narration.state === 'speaking' || narration.loading) return;
    const timer = window.setTimeout(() => {
      // Не сворачиваем под курсором и под фокусом клавиатуры.
      if (!hovered.current && !rootRef.current?.contains(document.activeElement)) setMode('idle');
    }, narration.state === 'completed' ? SPEAK_DONE_MS : SPEAK_IDLE_MS);
    return () => window.clearTimeout(timer);
  }, [speaking, narration.state, narration.loading]);

  // Реплики в покое сменяют друг друга — помощник выглядит живым, но не мешает.
  useEffect(() => {
    if (mode !== 'idle' || reduceMotion || teasers.length < 2) return;
    const timer = window.setInterval(() => setTeaserIndex((index) => index + 1), TEASER_MS);
    return () => window.clearInterval(timer);
  }, [mode, reduceMotion, teasers.length]);

  useEffect(() => {
    if (open && hasOffer) seenOffer?.();
  }, [hasOffer, open, seenOffer]);

  // Диктор читает только реплику, пришедшую сейчас, а не восстановленный диалог.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
    const reply = messages.filter((message) => message.role === 'tutor' && message.id.startsWith('local-')
      && !announced.current.has(message.id)).at(-1);
    messages.forEach((message) => announced.current.add(message.id));
    if (!reply) return;
    setAnnouncement('');
    requestAnimationFrame(() => setAnnouncement(reply.text));
  }, [messages, pending, open]);

  // Свернуть; с клавиатуры фокус возвращается на плашку, чтобы ученик не потерял место.
  const collapse = (returnFocus: boolean) => {
    if (narration.state === 'speaking') narration.pause();
    setMode('idle');
    if (returnFocus) requestAnimationFrame(() => idleRef.current?.focus({ preventScroll: true }));
  };

  // Щелчок мимо или Esc сворачивают чат; Esc сворачивает и реплику рассказчика.
  useEffect(() => {
    if (speaking) {
      const escapeSpeech = (event: KeyboardEvent) => { if (event.key === 'Escape') collapse(true); };
      document.addEventListener('keydown', escapeSpeech);
      return () => document.removeEventListener('keydown', escapeSpeech);
    }
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) collapse(false);
    };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') collapse(true); };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open, speaking]); // eslint-disable-line react-hooks/exhaustive-deps

  const expand = () => {
    if (!tutor) {
      // Без тьютора плашка — рассказчик: нажатие включает реплику.
      setMode('speak');
      narration.toggle();
      return;
    }
    setMode('open');
    // На итоговом задании поле закрыто — фокус на кнопку «Свернуть».
    requestAnimationFrame(() => (locked ? collapseRef.current : inputRef.current)?.focus({ preventScroll: true }));
  };

  // Наведение — только мышью: на телефоне касание сразу открывает чат.
  const hover = (event: ReactPointerEvent, entering: boolean) => {
    if (event.pointerType !== 'mouse') return;
    hovered.current = entering;
    if (!tutor) return;
    setMode((current) => (entering ? (current === 'idle' ? 'peek' : current) : (current === 'peek' && !draft ? 'idle' : current)));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.trim() || pending) return;
    tutor?.sendMessage(draft);
    setDraft('');
    setMode('open');
  };

  const ask = (action: () => void) => { action(); setMode('open'); };

  return (
    <div ref={rootRef} className="relative h-12 w-full" aria-live="off">
      <p className="sr-only" aria-live="polite">{announcement}</p>
      <div
        className={`absolute left-0 z-[75] transition-[width] duration-300 ease-out motion-reduce:transition-none ${WIDTH[mode]} ${mode === 'speak' ? 'bottom-[calc(100%+0.5rem)] lg:bottom-0' : 'bottom-0'}`}
        onPointerEnter={(event) => hover(event, true)}
        onPointerLeave={(event) => hover(event, false)}
      >
        <div className="overflow-hidden rounded-[26px] border border-white/10 bg-neutral-900/95 text-white shadow-2xl backdrop-blur-xl">
          <AnimatePresence initial={false}>
            {speaking && cueText && (
              <motion.section key="speech" aria-label={`Реплика: ${companion?.name || 'рассказчик'}`}
                initial={reduceMotion ? false : { height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                exit={reduceMotion ? undefined : { height: 0, opacity: 0 }} transition={{ duration: 0.28, ease: 'easeOut' }}>
                <div className="flex gap-3 px-4 pt-3">
                  {narration.video ? (
                    <video ref={narration.video.ref} src={narration.video.src} poster={narration.video.poster} playsInline preload="metadata"
                      muted={narration.video.muted} onPlay={narration.video.onPlay} onPause={narration.video.onPause}
                      onEnded={narration.video.onEnded} onTimeUpdate={narration.video.onTimeUpdate}
                      className="h-24 w-20 shrink-0 rounded-2xl bg-black/30 object-cover" />
                  ) : companion?.previewImageUrl ? (
                    <img src={companion.previewImageUrl} alt="" className="h-20 w-16 shrink-0 rounded-2xl object-cover object-top" />
                  ) : null}
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-semibold text-white/50">{companion?.name || 'Рассказчик'}</p>
                    <p className="mt-1 line-clamp-4 text-sm leading-relaxed">
                      {narration.state === 'speaking' && narration.activeSentence ? narration.activeSentence : cueText}
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 px-4 pb-2 pt-2">
                  <button type="button" onClick={narration.toggle}
                    className="inline-flex min-h-[40px] items-center gap-1.5 rounded-full bg-white px-4 text-xs font-semibold text-neutral-900">
                    {narration.loading ? <><Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> Загружаю…</>
                      : narration.state === 'speaking' ? <><Pause className="h-3.5 w-3.5" aria-hidden /> Пауза</>
                      : narration.state === 'completed' ? <><RotateCcw className="h-3.5 w-3.5" aria-hidden /> Ещё раз</>
                        : <><Play className="h-3.5 w-3.5" aria-hidden /> Послушать</>}
                  </button>
                  <button type="button" onClick={() => { narration.pause(); companion?.onAvatarEnabledChange(false); setMode('idle'); }}
                    className="inline-flex min-h-[40px] items-center gap-1.5 rounded-full border border-white/15 px-3 text-xs font-semibold text-white/75 hover:bg-white/10">
                    <EyeOff className="h-3.5 w-3.5" aria-hidden /> Не показывать рассказчика
                  </button>
                  <button type="button" onClick={() => collapse(true)} aria-label="Свернуть"
                    className="ml-auto grid h-10 w-10 place-items-center rounded-full text-white/60 hover:bg-white/10 hover:text-white">
                    <ChevronDown className="h-5 w-5" />
                  </button>
                </div>
              </motion.section>
            )}
            {open && tutor && (
              <motion.section
                key="chat"
                id={chatId}
                aria-label="Помощник"
                initial={reduceMotion ? false : { height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={reduceMotion ? undefined : { height: 0, opacity: 0 }}
                transition={{ duration: 0.28, ease: 'easeOut' }}
              >
                <div className="flex items-center justify-between px-4 pt-3">
                  <div>
                    <p className="text-sm font-semibold">Помощник</p>
                    <p className="text-[11px] text-white/50">Учитель может посмотреть этот диалог</p>
                  </div>
                  <button ref={collapseRef} type="button" onClick={() => collapse(true)} aria-label="Свернуть помощника"
                    className="grid h-11 w-11 place-items-center rounded-full text-white/60 hover:bg-white/10 hover:text-white">
                    <ChevronDown className="h-5 w-5" />
                  </button>
                </div>
                <div className="max-h-[min(45vh,420px)] space-y-2 overflow-y-auto px-4 py-2" aria-busy={pending}>
                  {messages.length === 0 && !pending && (
                    <p className="text-sm text-white/60">
                      {locked
                        ? 'Это итоговое задание — здесь ты справляешься сам. Если что-то забыл, вернись к объяснению.'
                        : 'Попроси подсказку или напиши, что непонятно — разберём по шагам.'}
                    </p>
                  )}
                  {messages.map((message) => (
                    <div key={message.id} className={message.role === 'student' ? 'flex justify-end' : 'flex justify-start'}>
                      <div className={`max-w-[88%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                        message.role === 'student' ? 'bg-primary text-primary-foreground' : 'bg-white/10'}`}>
                        {message.role === 'tutor' ? parseMathText(message.text) : message.text}
                        {message.role === 'tutor' && ((message.offer && message === lastReply) || typeof message.theoryStep === 'number') && (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {message.offer && message === lastReply && !locked && (
                              <button type="button" onClick={tutor?.requestHint} disabled={pending}
                                className="min-h-[44px] rounded-full bg-white/15 px-4 text-xs font-semibold hover:bg-white/25 disabled:opacity-50">
                                Да, помоги
                              </button>
                            )}
                            {typeof message.theoryStep === 'number' && (
                              <button type="button" onClick={() => { tutor?.openTheory(message.theoryStep as number); setMode('idle'); }}
                                className="inline-flex min-h-[44px] items-center gap-1 rounded-full bg-white/15 px-4 text-xs font-semibold hover:bg-white/25">
                                <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> К объяснению
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                  {pending && (
                    <div className="flex items-center gap-2 text-xs text-white/60">
                      <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden /> Помощник думает…
                    </div>
                  )}
                  <div ref={endRef} />
                </div>
                {!locked && (
                  <div className="flex flex-wrap gap-1.5 px-4 pb-2">
                    {companion?.cue && !companion.avatarEnabled && (
                      <button type="button" onClick={() => companion.onAvatarEnabledChange(true)}
                        className="inline-flex min-h-[44px] items-center gap-1 rounded-full border border-white/15 px-3 text-xs font-semibold text-white/85 hover:bg-white/10">
                        <UserRound className="h-3.5 w-3.5" aria-hidden /> Вернуть рассказчика
                      </button>
                    )}
                    {narrator && (
                      <button type="button" onClick={() => { setMode('speak'); narration.toggle(); }}
                        className="inline-flex min-h-[44px] items-center gap-1 rounded-full border border-white/15 px-3 text-xs font-semibold text-white/85 hover:bg-white/10">
                        <Volume2 className="h-3.5 w-3.5" aria-hidden /> Объяснение шага
                      </button>
                    )}
                    <button type="button" onClick={() => ask(() => tutor?.requestHint())} disabled={pending}
                      className="inline-flex min-h-[44px] items-center gap-1 rounded-full border border-white/15 px-3 text-xs font-semibold text-white/85 hover:bg-white/10 disabled:opacity-50">
                      <Lightbulb className="h-3.5 w-3.5" aria-hidden /> Подсказка
                    </button>
                    <button type="button" onClick={() => ask(() => tutor?.sendMessage(STUCK_MESSAGE))} disabled={pending}
                      className="min-h-[44px] rounded-full border border-white/15 px-3 text-xs font-semibold text-white/85 hover:bg-white/10 disabled:opacity-50">
                      {STUCK_MESSAGE}
                    </button>
                    <button type="button" onClick={() => { setDraft((current) => current || 'Я думаю так: '); inputRef.current?.focus(); }} disabled={pending}
                      className="min-h-[44px] rounded-full border border-white/15 px-3 text-xs font-semibold text-white/85 hover:bg-white/10 disabled:opacity-50">
                      Проверь мою мысль
                    </button>
                  </div>
                )}
              </motion.section>
            )}
          </AnimatePresence>

          {/* При наведении — последняя реплика помощника, как строка над полем ввода. */}
          {mode === 'peek' && lastReply && (
            <button type="button" onClick={expand}
              className="flex w-full items-center gap-3 border-b border-white/10 px-4 py-2.5 text-left text-sm text-white/70 hover:text-white">
              <span className="shrink-0 text-white/45">Последняя реплика</span>
              <span className="min-w-0 flex-1 truncate">{lastReply.text.replace(/\$/g, '')}</span>
              <ChevronRight className="h-4 w-4 shrink-0" aria-hidden />
            </button>
          )}

          {mode === 'idle' || mode === 'speak' || !tutor ? (
            <button ref={idleRef} type="button" onClick={expand} aria-expanded={false} aria-controls={chatId}
              aria-label={hasOffer ? `Помощник: ${teaser}` : 'Открыть помощника'}
              className="flex h-12 w-full items-center gap-2 px-2 pr-4 text-left">
              <TutorOrb calling={hasOffer} imageUrl={faceUrl} narrator={narrator} speaking={narration.state === 'speaking'} />
              <span className="relative h-5 min-w-0 flex-1 overflow-hidden text-sm text-white/75">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span
                    key={teaser}
                    className="absolute inset-0 truncate"
                    initial={reduceMotion ? false : { y: 12, opacity: 0 }}
                    animate={{ y: 0, opacity: 1 }}
                    exit={reduceMotion ? undefined : { y: -12, opacity: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    {teaser}
                  </motion.span>
                </AnimatePresence>
              </span>
              {hasOffer && <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-primary" aria-hidden />}
            </button>
          ) : (
            <form onSubmit={submit} className="flex h-12 items-center gap-2 px-2">
              <TutorOrb calling={hasOffer && !open} imageUrl={faceUrl} narrator={narrator} speaking={narration.state === 'speaking'} />
              <input
                ref={inputRef}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onFocus={() => setMode('open')}
                disabled={locked}
                maxLength={500}
                placeholder={locked ? 'На итоговом задании помощник молчит' : 'Спроси помощника…'}
                aria-label="Сообщение помощнику"
                className="h-10 min-w-0 flex-1 bg-transparent text-sm text-white placeholder:text-white/45 focus:outline-none disabled:cursor-not-allowed"
              />
              <button type="submit" disabled={pending || locked || !draft.trim()} aria-label="Отправить"
                className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-white text-neutral-900 transition-opacity disabled:opacity-30">
                <Send className="h-4 w-4" aria-hidden />
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
