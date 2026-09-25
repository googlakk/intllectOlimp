import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError } from '@/lib/api/client';
import { postTutorTurn, useTutorSession, type TutorEvent, type TutorOutcome } from '@/lib/api/tutor';
import type { Block } from '@/lib/api/types';
import { IdleTimer } from './idleTimer';
import { TUTOR_ATTEMPT_COMPONENTS, type TutorAttempt, type TutorBridge } from './tutorBridge';
import { isRepeatAttempt, isTutorLocked, resolveTheoryStep, sessionToMessages, type TutorMessage } from './tutorRules';

const IDLE_DELAY_MS = 60_000;
const UNAVAILABLE = 'Помощник сейчас недоступен. Попробуй ещё раз чуть позже.';

type UseLessonTutorParams = {
  topicId: number;
  studentId: number | undefined;
  /** Только ученик: у учителя и в предпросмотре помощника нет. */
  enabled: boolean;
  /** Ответы урока (исходный индекс → верно): решённая раньше задача не зовёт помощника по бездействию. */
  answers: Record<string, boolean>;
  /** «Попробовать снова» пересоздаёт блок (ключ по шагу маршрута) — помощь снова уместна. */
  retryKeys: Record<number, number>;
  activeBlocks: Block[];
  activeOriginalIndices: number[];
  currentStep: number;
  maxOpenedStep: number;
  onNavigate: (step: number) => void;
};

export type LessonTutor = {
  available: boolean;
  locked: boolean;
  pending: boolean;
  messages: TutorMessage[];
  hasOffer: boolean;
  bridge: TutorBridge;
  sendMessage: (text: string) => void;
  requestHint: () => void;
  openTheory: (step: number) => void;
  seenOffer: () => void;
};

type SendOptions = { message?: string; value?: string; outcome?: TutorOutcome; blockIndex?: number; stepIndex?: number };

/**
 * Тьютор внутри урока: слушает попытки блоков, бездействие и сообщения ученика.
 * Урок ведёт маршрут — тьютор может только предложить вернуться к объяснению;
 * пути к «Дальше» и завершению урока у него нет.
 */
export function useLessonTutor({
  topicId, studentId, enabled, answers, retryKeys, activeBlocks, activeOriginalIndices, currentStep, maxOpenedStep, onNavigate,
}: UseLessonTutorParams): LessonTutor {
  const session = useTutorSession(topicId, studentId, enabled);
  const [disabled, setDisabled] = useState(false);
  const block = activeBlocks[currentStep];
  // На итоговом экране урока (шаг за последним блоком) задания нет — помощника тоже.
  const available = enabled && !disabled && session.data?.enabled === true && Boolean(block);
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [pendingBlocks, setPendingBlocks] = useState<Readonly<Record<number, number>>>({});
  const [offerBlocks, setOfferBlocks] = useState<ReadonlySet<number>>(new Set());
  const blockIndex = activeOriginalIndices[currentStep] ?? currentStep;
  const locked = isTutorLocked(block);

  // Актуальные значения для асинхронных ответов: пока тьютор думал, ученик мог уйти на другой шаг.
  const route = useRef({ activeOriginalIndices, currentStep, maxOpenedStep, blockIndex });
  route.current = { activeOriginalIndices, currentStep, maxOpenedStep, blockIndex };
  const nextId = useRef(0);
  const lastAttempt = useRef<TutorAttempt | null>(null);
  // Задачи, где помощь по бездействию уже не нужна: решены или закрыты после всех попыток.
  const doneBlocks = useRef(new Set<number>());
  const answersRef = useRef(answers);
  answersRef.current = answers;
  const restoredFor = useRef<number | null>(null);

  useEffect(() => {
    if (!session.data || restoredFor.current === topicId) return;
    restoredFor.current = topicId;
    setMessages(sessionToMessages(session.data.turns));
  }, [session.data, topicId]);

  const append = useCallback((message: Omit<TutorMessage, 'id'>) => {
    nextId.current += 1;
    setMessages((current) => [...current, { ...message, id: `local-${nextId.current}` }]);
  }, []);

  const markPending = useCallback((target: number, delta: number) => {
    setPendingBlocks((current) => ({ ...current, [target]: Math.max(0, (current[target] ?? 0) + delta) }));
  }, []);

  const send = useCallback(async (event: TutorEvent, options: SendOptions = {}) => {
    if (!available) return;
    const target = options.blockIndex ?? route.current.blockIndex;
    const step = options.stepIndex ?? route.current.currentStep;
    const speaks = event === 'message' || event === 'hint_requested';
    if (options.message) append({ role: 'student', text: options.message, blockIndex: target });
    if (speaks) markPending(target, 1);
    try {
      const response = await postTutorTurn({
        topic_id: topicId, block_index: target, step_index: step, event,
        message: options.message ?? null, student_value: options.value ?? null, client_outcome: options.outcome ?? null,
      });
      if (!response.reply) return;
      const { activeOriginalIndices: indices, currentStep: now, maxOpenedStep: opened } = route.current;
      append({
        role: 'tutor', text: response.reply, blockIndex: target, offer: response.offer,
        theoryStep: resolveTheoryStep(response.action, indices, now, opened),
      });
      if (response.offer) setOfferBlocks((current) => new Set(current).add(target));
    } catch (error) {
      // Выключен для школы или таблица недоступна — прячем помощника, урок идёт дальше.
      if (error instanceof ApiError && (error.status === 403 || error.status === 503)) setDisabled(true);
      if (speaks) append({ role: 'tutor', text: UNAVAILABLE, blockIndex: target });
    } finally {
      if (speaks) markPending(target, -1);
    }
  }, [append, available, markPending, topicId]);

  // Блок пересоздан кнопкой «Попробовать снова» — считаем задачу снова открытой.
  const previousRetryKeys = useRef(retryKeys);
  useEffect(() => {
    Object.entries(retryKeys).forEach(([step, key]) => {
      if (previousRetryKeys.current[Number(step)] === key) return;
      const retried = activeOriginalIndices[Number(step)] ?? Number(step);
      doneBlocks.current.delete(retried);
      if (lastAttempt.current?.blockIndex === retried) lastAttempt.current = null;
    });
    previousRetryKeys.current = retryKeys;
  }, [activeOriginalIndices, retryKeys]);

  const bridge = useMemo<TutorBridge>(() => (available ? {
    onAttempt: (attempt) => {
      if (isRepeatAttempt(lastAttempt.current, attempt)) return;
      lastAttempt.current = attempt;
      if (attempt.outcome === 'correct' || attempt.locked) doneBlocks.current.add(attempt.blockIndex);
      void send('answer_submitted', {
        value: attempt.value, outcome: attempt.outcome, blockIndex: attempt.blockIndex, stepIndex: attempt.stepIndex,
      });
    },
  } : {}), [available, send]);

  // Бездействие: один раз на шаге-задаче, пока задача не решена.
  const idleEligible = available && !locked && Boolean(block && TUTOR_ATTEMPT_COMPONENTS.has(block.component));
  useEffect(() => {
    if (!idleEligible) return;
    const timer = new IdleTimer(IDLE_DELAY_MS, () => {
      const done = doneBlocks.current.has(blockIndex) || answersRef.current[String(blockIndex)] === true;
      if (!done) void send('idle', { blockIndex, stepIndex: currentStep });
    });
    const activity = () => { if (!document.hidden) timer.reset(); };
    const visibility = () => (document.hidden ? timer.stop() : timer.reset());
    const events = ['pointerdown', 'keydown', 'input', 'wheel'] as const;
    events.forEach((name) => window.addEventListener(name, activity, { passive: true }));
    document.addEventListener('visibilitychange', visibility);
    timer.reset(true);
    return () => {
      timer.stop();
      events.forEach((name) => window.removeEventListener(name, activity));
      document.removeEventListener('visibilitychange', visibility);
    };
  }, [blockIndex, currentStep, idleEligible, send]);

  const sendMessage = useCallback((text: string) => {
    const message = text.trim().slice(0, 500);
    if (message) void send('message', { message });
  }, [send]);
  const requestHint = useCallback(() => void send('hint_requested'), [send]);
  const openTheory = useCallback((step: number) => {
    const { currentStep: now, maxOpenedStep: opened } = route.current;
    if (step < now && step <= opened) onNavigate(step);
  }, [onNavigate]);
  const seenOffer = useCallback(() => {
    setOfferBlocks((current) => {
      if (!current.has(route.current.blockIndex)) return current;
      const next = new Set(current);
      next.delete(route.current.blockIndex);
      return next;
    });
  }, []);

  return {
    available,
    locked,
    pending: (pendingBlocks[blockIndex] ?? 0) > 0,
    messages: useMemo(() => messages.filter((message) => message.blockIndex === blockIndex), [blockIndex, messages]),
    hasOffer: offerBlocks.has(blockIndex),
    bridge,
    sendMessage,
    requestHint,
    openTheory,
    seenOffer,
  };
}
