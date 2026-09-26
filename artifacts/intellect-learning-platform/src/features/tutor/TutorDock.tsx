import { useEffect, useId, useMemo, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { ArrowLeft, ChevronDown, EyeOff, Lightbulb, Loader2, MessageCircle, Mic, Pause, Play, RotateCcw, Send, UserRound, Volume2, X } from 'lucide-react';
import type { AvatarCue } from '@/lib/api/types';
import { useAvatarNarration } from '@/features/lessons/useAvatarNarration';
import { useIsMobile } from '@/hooks/use-mobile';
import { parseMathText } from '@/components/blocks/ShortExplanation';
import { tutorTeasers } from './tutorRules';
import type { LessonTutor } from './useLessonTutor';

/**
 * Состояния помощника:
 * stage — открытие урока: крупный аватар поверх урока ждёт нажатия, потом говорит с субтитрами;
 * idle  — после реплики: маленький аватар и поле «Задайте вопрос…»;
 * speak — наведение или новая реплика: пузырь над аватаром с текстом и «Повторить»;
 * open  — разговор с тьютором.
 */
type DockMode = 'idle' | 'stage' | 'speak' | 'open';

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
const SPEAK_IDLE_MS = 9000;
const SPEAK_DONE_MS = 2500;
// Крупная сцена после реплики сворачивается в маленький аватар.
const STAGE_DONE_MS = 1200;
const STUCK_MESSAGE = 'Не понимаю, что делать';
// Золотое кольцо рассказчика — как в макете: персонаж урока, а не кнопка интерфейса.
const RING = 'ring-2 ring-amber-300/80 shadow-[0_0_24px_rgba(251,191,36,0.35)]';

type Narration = ReturnType<typeof useAvatarNarration>;

function readFlag(key: string): boolean {
  try { return sessionStorage.getItem(key) === '1'; } catch { return false; }
}
function writeFlag(key: string): void {
  try { sessionStorage.setItem(key, '1'); } catch { /* приватный режим — сцена может выйти ещё раз */ }
}

/** Лицо рассказчика в круге: видео реплики, если оно есть, иначе портрет. Говорит — расходятся кольца. */
function AvatarFace({ narration, imageUrl, size, withVideo, speaking }: {
  narration: Narration; imageUrl?: string | null; size: string; withVideo: boolean; speaking: boolean;
}) {
  const reduceMotion = useReducedMotion();
  const video = withVideo ? narration.video : null;
  return (
    <span className={`relative grid shrink-0 place-items-center rounded-full ${size}`} aria-hidden>
      {speaking && !reduceMotion && [0, 0.6].map((delay) => (
        <motion.span key={delay} className="absolute inset-0 rounded-full border-2 border-amber-300/60"
          animate={{ scale: [1, 1.18], opacity: [0.7, 0] }} transition={{ duration: 1.6, delay, repeat: Infinity, ease: 'easeOut' }} />
      ))}
      <span className={`relative block h-full w-full overflow-hidden rounded-full bg-neutral-800 ${RING}`}>
        {video ? (
          <video ref={video.ref} src={video.src} poster={video.poster || imageUrl || undefined} playsInline preload={video.preload}
            muted={video.muted} onPlay={video.onPlay} onPause={video.onPause} onEnded={video.onEnded} onError={video.onError}
            onTimeUpdate={video.onTimeUpdate} className="h-full w-full object-cover object-top" />
        ) : imageUrl ? (
          <img src={imageUrl} alt="" className="h-full w-full object-cover object-top" />
        ) : (
          <span className="grid h-full w-full place-items-center text-amber-200"><UserRound className="h-1/2 w-1/2" /></span>
        )}
      </span>
    </span>
  );
}

/** Звуковая волна под субтитрами: движется, пока рассказчик говорит. */
function Waveform({ active }: { active: boolean }) {
  const reduceMotion = useReducedMotion();
  const bars = [3, 5, 8, 12, 7, 14, 9, 16, 10, 6, 12, 8, 5, 3];
  return (
    <span className="mt-3 flex h-5 items-center justify-center gap-[3px]" aria-hidden>
      {bars.map((height, index) => (
        <motion.span key={index} className="w-[3px] rounded-full bg-amber-300/80" style={{ height }}
          animate={active && !reduceMotion ? { scaleY: [0.35, 1, 0.5, 0.9, 0.35] } : { scaleY: 0.3 }}
          transition={{ duration: 1.1, delay: index * 0.06, repeat: active && !reduceMotion ? Infinity : 0, ease: 'easeInOut' }} />
      ))}
    </span>
  );
}

/** Кнопка озвучки: Послушать / Загружаю / Пауза / Повторить. */
function NarrationButton({ narration, onClick }: { narration: Narration; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick}
      className="inline-flex min-h-[44px] items-center gap-2 rounded-full border border-amber-300/70 px-4 text-sm font-semibold text-amber-100 transition-colors hover:bg-amber-300/10">
      {narration.loading ? <><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Загружаю…</>
        : narration.state === 'speaking' ? <><Pause className="h-4 w-4" aria-hidden /> Пауза</>
          : narration.state === 'completed' ? <><RotateCcw className="h-4 w-4" aria-hidden /> Повторить</>
            : <><Play className="h-4 w-4 fill-current" aria-hidden /> Послушать</>}
    </button>
  );
}

/**
 * Помощник урока внизу слева: рассказчик (аватар) и тьютор — один персонаж.
 * На открытии урока рассказчик выходит крупно, дальше живёт маленьким аватаром у поля вопроса.
 */
export function TutorDock({ tutor, companion }: { tutor?: LessonTutor; companion?: CompanionInput }) {
  const [mode, setMode] = useState<DockMode>('idle');
  const [draft, setDraft] = useState('');
  const [teaserIndex, setTeaserIndex] = useState(0);
  const [announcement, setAnnouncement] = useState('');
  const reduceMotion = useReducedMotion();
  // На телефоне строку делит «Продолжить»: поле вопроса — внутри чата.
  const mobile = useIsMobile();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const avatarRef = useRef<HTMLButtonElement>(null);
  const collapseRef = useRef<HTMLButtonElement>(null);
  const stageStartRef = useRef<HTMLButtonElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
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
  const staged = mode === 'stage';
  const hovered = useRef(false);
  const narration = useAvatarNarration({
    cue: companion?.cue, lessonVersionId: companion?.lessonVersionId,
    avatarEnabled: companion?.avatarEnabled ?? false, audioEnabled: companion?.audioEnabled ?? false,
    onAudioEnabledChange: companion?.onAudioEnabledChange ?? (() => undefined),
  });
  const cueText = companion?.avatarEnabled ? narration.narration : '';
  const faceUrl = companion?.avatarEnabled ? companion?.previewImageUrl : null;
  const narrator = Boolean(cueText);
  const name = companion?.name || 'Рассказчик';
  const talking = narration.state === 'speaking';
  const subtitle = talking && narration.activeSentence ? narration.activeSentence : cueText;
  const lastReply = useMemo(() => messages.filter((message) => message.role === 'tutor').at(-1), [messages]);
  const teasers = tutorTeasers({ locked, hasOffer, lastReply: lastReply?.text });
  const teaser = teasers[teaserIndex % teasers.length];

  // Первая реплика урока — крупная сцена; новая реплика на следующих шагах — пузырь над аватаром.
  const cueKey = `${companion?.cue?.id ?? ''}:${companion?.cue?.beat_id ?? ''}`;
  // Сама выходит один раз на реплику: при возврате на шаг — только по нажатию.
  const shownCues = useRef(new Set<string>());
  // Крупная сцена — один раз за урок в этой вкладке: после перезагрузки посреди урока не выходит снова.
  const stageKey = `intellect-avatar-stage:${companion?.lessonVersionId ?? ''}`;
  const stageShown = useRef(readFlag(stageKey));
  useEffect(() => {
    const firstTime = Boolean(cueText) && !shownCues.current.has(cueKey);
    if (firstTime) shownCues.current.add(cueKey);
    if (firstTime && !stageShown.current) {
      stageShown.current = true;
      writeFlag(stageKey);
      setMode((current) => (current === 'open' ? current : 'stage'));
      return;
    }
    // На шаге без реплики пузырь и сцена уходят.
    setMode((current) => (current === 'open' ? current : firstTime ? 'speak' : current === 'speak' || current === 'stage' ? 'idle' : current));
  }, [cueKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // Свернуть; с клавиатуры фокус возвращается на аватар, чтобы ученик не потерял место.
  const collapse = (returnFocus: boolean) => {
    if (talking || narration.loading) narration.pause();
    setMode('idle');
    if (returnFocus) requestAnimationFrame(() => avatarRef.current?.focus({ preventScroll: true }));
  };

  // Ушли из реплики (открыли чат, сменился шаг) — озвучку на паузу: иначе она звучит без кнопок.
  useEffect(() => {
    if (!speaking && !staged && (talking || narration.loading)) narration.pause();
  }, [mode, talking, narration.loading]); // eslint-disable-line react-hooks/exhaustive-deps

  // Пузырь сам сворачивается, если его не слушают; сцена — после конца реплики.
  useEffect(() => {
    if (staged) {
      if (narration.state !== 'completed') return undefined;
      // Фокус был в окне сцены — возвращаем его на аватар, а не теряем на body.
      const timer = window.setTimeout(() => collapse(true), STAGE_DONE_MS);
      return () => window.clearTimeout(timer);
    }
    if (!speaking || talking || narration.loading) return undefined;
    const timer = window.setTimeout(() => {
      // Не сворачиваем под курсором и под фокусом клавиатуры.
      if (!hovered.current && !rootRef.current?.contains(document.activeElement)) setMode('idle');
    }, narration.state === 'completed' ? SPEAK_DONE_MS : SPEAK_IDLE_MS);
    return () => window.clearTimeout(timer);
  }, [speaking, staged, talking, narration.loading, narration.state]); // eslint-disable-line react-hooks/exhaustive-deps

  // Подсказки тьютора в поле ввода сменяют друг друга — помощник выглядит живым, но не мешает.
  useEffect(() => {
    if (mode !== 'idle' || reduceMotion || teasers.length < 2) return undefined;
    const timer = window.setInterval(() => setTeaserIndex((index) => index + 1), 5000);
    return () => window.clearInterval(timer);
  }, [mode, reduceMotion, teasers.length]);

  useEffect(() => {
    if (open && hasOffer) seenOffer?.();
  }, [hasOffer, open, seenOffer]);

  // Сцена — модальное окно: урок под ней недоступен для Tab и экранного диктора, фокус внутри окна.
  useEffect(() => {
    if (!staged) return undefined;
    const app = document.getElementById('root');
    app?.setAttribute('inert', '');
    requestAnimationFrame(() => stageStartRef.current?.focus({ preventScroll: true }));
    const trap = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !stageRef.current) return;
      const focusable = Array.from(stageRef.current.querySelectorAll<HTMLElement>('button:not([disabled])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      else if (!stageRef.current.contains(document.activeElement)) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', trap);
    return () => {
      app?.removeAttribute('inert');
      document.removeEventListener('keydown', trap);
    };
  }, [staged]);

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

  // Esc сворачивает сцену, пузырь и чат; щелчок мимо сворачивает чат.
  useEffect(() => {
    if (!open && !speaking && !staged) return undefined;
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      // Esc в чужом окне (картинка, всплывающее меню) не трогает помощника.
      const inside = rootRef.current?.contains(document.activeElement) || stageRef.current?.contains(document.activeElement);
      if (staged || inside) collapse(true);
    };
    document.addEventListener('keydown', escape);
    if (!open) return () => document.removeEventListener('keydown', escape);
    const outside = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) collapse(false);
    };
    document.addEventListener('pointerdown', outside);
    return () => {
      document.removeEventListener('keydown', escape);
      document.removeEventListener('pointerdown', outside);
    };
  }, [open, speaking, staged]); // eslint-disable-line react-hooks/exhaustive-deps

  const openChat = () => {
    setMode('open');
    // На итоговом задании поле закрыто — фокус на кнопку «Свернуть».
    requestAnimationFrame(() => (locked ? collapseRef.current : inputRef.current)?.focus({ preventScroll: true }));
  };
  // Нажатие на аватар: у рассказчика — пузырь с репликой, иначе — чат тьютора.
  const pressAvatar = () => {
    if (narrator) { setMode(speaking ? 'idle' : 'speak'); return; }
    if (tutor) openChat();
  };

  // Наведение мышью на аватар раскрывает пузырь; уход — сворачивает, если реплика не звучит.
  // Закрываем с задержкой: курсор успевает перейти через зазор с аватара на пузырь.
  const leaveTimer = useRef<number | null>(null);
  useEffect(() => () => { if (leaveTimer.current) window.clearTimeout(leaveTimer.current); }, []);
  const hover = (event: ReactPointerEvent, entering: boolean) => {
    if (event.pointerType !== 'mouse') return;
    hovered.current = entering;
    if (leaveTimer.current) { window.clearTimeout(leaveTimer.current); leaveTimer.current = null; }
    if (!narrator) return;
    if (entering) { setMode((current) => (current === 'idle' ? 'speak' : current)); return; }
    leaveTimer.current = window.setTimeout(() => {
      leaveTimer.current = null;
      if (hovered.current || talking || narration.loading || rootRef.current?.contains(document.activeElement)) return;
      setMode((current) => (current === 'speak' ? 'idle' : current));
    }, 250);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!draft.trim() || pending) return;
    tutor?.sendMessage(draft);
    setDraft('');
    setMode('open');
  };

  const ask = (action: () => void) => { action(); setMode('open'); };

  const questionForm = (
          <form onSubmit={submit}
            className="flex h-12 min-w-0 flex-1 items-center gap-2 rounded-full border border-white/10 bg-neutral-900/95 pl-4 pr-1.5 text-white shadow-lg backdrop-blur-xl">
            <input
              ref={inputRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onFocus={() => setMode('open')}
              disabled={locked}
              maxLength={500}
              placeholder={locked ? 'На итоговом задании помощник молчит' : hasOffer ? teaser : 'Задайте вопрос…'}
              aria-label="Сообщение помощнику"
              aria-controls={chatId}
              className="h-10 min-w-0 flex-1 bg-transparent text-sm text-white placeholder:text-white/50 focus:outline-none disabled:cursor-not-allowed"
            />
            <button type="submit" disabled={pending || locked || !draft.trim()} aria-label="Отправить"
              className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-white/80 transition-colors hover:bg-white/10 disabled:opacity-40">
              <Send className="h-4 w-4" aria-hidden />
            </button>
          </form>
  );

  const stage = typeof document !== 'undefined' && createPortal(
    <AnimatePresence>
      {staged && narrator && (
        <motion.div key="stage" ref={stageRef} role="dialog" aria-modal="true" aria-label={`${name}: вступление к уроку`}
          className="fixed inset-0 z-[90] flex flex-col items-center justify-center bg-neutral-950/75 px-4 backdrop-blur-sm"
          initial={reduceMotion ? false : { opacity: 0 }} animate={{ opacity: 1 }}
          exit={reduceMotion ? undefined : { opacity: 0 }} transition={{ duration: 0.3 }}>
          <button type="button" onClick={() => collapse(true)}
            className="absolute right-4 top-4 inline-flex min-h-[44px] items-center gap-1.5 rounded-full px-4 text-sm font-semibold text-white/70 hover:bg-white/10 hover:text-white">
            Пропустить <X className="h-4 w-4" aria-hidden />
          </button>
          <motion.div className="flex w-full max-w-xl flex-col items-center"
            initial={reduceMotion ? false : { scale: 0.9, y: 16 }} animate={{ scale: 1, y: 0 }}
            // Уходя, сцена «улетает» к маленькому аватару внизу слева.
            exit={reduceMotion ? undefined : { scale: 0.3, x: '-38vw', y: '38vh', opacity: 0 }}
            transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}>
            <p className="mb-4 text-sm font-semibold uppercase tracking-wider text-amber-200/80">{name}</p>
            <div className="relative">
              <AvatarFace narration={narration} imageUrl={faceUrl} withVideo speaking={talking}
                size="h-[min(62vw,320px)] w-[min(62vw,320px)]" />
              {!talking && narration.state !== 'completed' && (
                <button ref={stageStartRef} type="button" onClick={narration.toggle}
                  className="absolute -bottom-6 left-1/2 inline-flex min-h-[56px] -translate-x-1/2 items-center gap-3 whitespace-nowrap rounded-full border border-amber-300/70 bg-neutral-900/95 px-6 text-sm font-medium text-white shadow-2xl hover:bg-neutral-800">
                  {narration.loading
                    ? <><Loader2 className="h-5 w-5 animate-spin text-amber-200" aria-hidden /> Загружаю…</>
                    : <><Mic className="h-5 w-5 text-amber-200" aria-hidden /> Нажмите, чтобы начать</>}
                </button>
              )}
            </div>
            <AnimatePresence>
              {(talking || narration.state === 'completed') && (
                <motion.div className="mt-8 w-full rounded-3xl border border-white/10 bg-neutral-900/90 px-6 py-5 text-center shadow-2xl"
                  initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                  <p className="text-base leading-relaxed text-white md:text-lg">{subtitle}</p>
                  <Waveform active={talking} />
                  {talking && (
                    <button type="button" onClick={narration.toggle}
                      className="mt-2 inline-flex min-h-[44px] items-center gap-1.5 rounded-full px-4 text-sm font-semibold text-white/60 hover:text-white">
                      <Pause className="h-4 w-4" aria-hidden /> Пауза
                    </button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );

  return (
    <div ref={rootRef} className="relative h-12 w-full lg:w-[min(520px,100%)]" aria-live="off">
      <p className="sr-only" aria-live="polite">{announcement}</p>
      {stage}

      <AnimatePresence initial={false}>
        {/* Пузырь рассказчика над аватаром: текст реплики и «Повторить». */}
        {speaking && narrator && (
          <motion.section key="bubble" aria-label={`Реплика: ${name}`}
            className="absolute bottom-[calc(100%+14px)] left-0 z-[75] w-[min(480px,calc(100vw-2rem))]"
            onPointerEnter={(event) => hover(event, true)} onPointerLeave={(event) => hover(event, false)}
            initial={reduceMotion ? false : { opacity: 0, y: 10, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 10, scale: 0.96 }} transition={{ duration: 0.22, ease: 'easeOut' }}
            style={{ transformOrigin: '24px 100%' }}>
            <div className="relative flex gap-4 rounded-3xl border border-amber-200/15 bg-neutral-900/95 p-4 text-white shadow-2xl backdrop-blur-xl">
              <AvatarFace narration={narration} imageUrl={faceUrl} withVideo speaking={talking} size="h-24 w-24 sm:h-28 sm:w-28" />
              <div className="min-w-0 flex-1">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-wider text-amber-200/70">{name}</p>
                  <button type="button" onClick={() => collapse(true)} aria-label="Свернуть"
                    className="-mr-2 -mt-2 grid h-10 w-10 shrink-0 place-items-center rounded-full text-white/50 hover:bg-white/10 hover:text-white">
                    <ChevronDown className="h-5 w-5" />
                  </button>
                </div>
                <p className="line-clamp-4 text-sm leading-relaxed">{subtitle}</p>
                {talking && <Waveform active />}
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <NarrationButton narration={narration} onClick={narration.toggle} />
                  <button type="button" onClick={() => { narration.pause(); companion?.onAvatarEnabledChange(false); setMode('idle'); }}
                    aria-label="Не показывать рассказчика" title="Не показывать рассказчика"
                    className="grid h-11 w-11 place-items-center rounded-full text-white/50 hover:bg-white/10 hover:text-white">
                    <EyeOff className="h-4 w-4" aria-hidden />
                  </button>
                </div>
              </div>
              {/* Хвостик пузыря — к аватару внизу. */}
              <span className="absolute -bottom-2 left-4 h-4 w-4 rotate-45 border-b border-r border-amber-200/15 bg-neutral-900" aria-hidden />
            </div>
          </motion.section>
        )}

        {open && tutor && (
          <motion.section key="chat" id={chatId} aria-label="Помощник"
            className="absolute bottom-[calc(100%+14px)] left-0 z-[75] w-[min(680px,calc(100vw-2rem))] overflow-hidden rounded-3xl border border-white/10 bg-neutral-900/95 text-white shadow-2xl backdrop-blur-xl"
            initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 12 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <div className="flex items-center justify-between px-4 pt-3">
              <div>
                <p className="text-sm font-semibold">{narrator ? name : 'Помощник'}</p>
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
              <div className="flex flex-wrap gap-1.5 px-4 pb-3">
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
            {mobile && <div className="px-3 pb-3">{questionForm}</div>}
          </motion.section>
        )}
      </AnimatePresence>

      {/* Строка помощника: маленький аватар и поле вопроса. */}
      <div className="flex h-12 items-center gap-3">
        <button ref={avatarRef} type="button" onClick={pressAvatar}
          onPointerEnter={(event) => hover(event, true)} onPointerLeave={(event) => hover(event, false)}
          aria-label={`${narrator ? `${name}: реплика шага` : 'Открыть помощника'}${hasOffer ? `. ${teaser}` : ''}`} aria-expanded={speaking || open}
          className="relative h-12 w-12 shrink-0 rounded-full">
          {narrator || faceUrl ? (
            <AvatarFace narration={narration} imageUrl={faceUrl} withVideo={false} speaking={false} size="h-12 w-12" />
          ) : (
            <span className="block h-12 w-12 rounded-full bg-gradient-to-br from-primary via-violet-400 to-sky-300 shadow-[0_0_14px_rgba(124,92,255,0.55)]" aria-hidden />
          )}
          {hasOffer && <span className="absolute right-0 top-0 h-3 w-3 rounded-full border-2 border-background bg-amber-400" aria-hidden />}
        </button>
        {tutor ? (
          mobile ? (
            // Телефон: строку делит «Продолжить» — поле ввода живёт в раскрытом чате во всю ширину.
            <button type="button" onClick={openChat} aria-expanded={open} aria-controls={chatId}
              className="flex h-12 min-w-0 flex-1 items-center justify-center gap-2 rounded-full border border-white/10 bg-neutral-900/95 px-4 text-sm font-semibold text-white/85 shadow-lg">
              <MessageCircle className="h-4 w-4 shrink-0 text-amber-200" aria-hidden /> Спросить
            </button>
          ) : questionForm
        ) : narrator ? (
          <button type="button" onClick={() => { setMode('speak'); narration.toggle(); }}
            className="flex h-12 min-w-0 flex-1 items-center gap-2 rounded-full border border-white/10 bg-neutral-900/95 px-4 text-left text-sm text-white/75 shadow-lg">
            <Play className="h-4 w-4 shrink-0 fill-current text-amber-200" aria-hidden />
            <span className="truncate">{name}: нажми, чтобы послушать</span>
          </button>
        ) : null}
      </div>
    </div>
  );
}
