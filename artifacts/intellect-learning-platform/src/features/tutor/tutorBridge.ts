import type { AnswerCheck } from '@/features/interactiveEngines/scoring';

/** Попытка ученика в блоке: само значение, а не только «верно/неверно». */
export type BlockAttempt = { value: string; outcome: AnswerCheck; hintsSeen?: number };

/** Попытка с местом в уроке: blockIndex — исходный индекс блока, stepIndex — позиция в маршруте. */
export type TutorAttempt = BlockAttempt & { blockIndex: number; stepIndex: number };

export type TutorBridge = { onAttempt?: (attempt: TutorAttempt) => void };

/** Предел длины ответа в API тьютора (student_value). */
export const ATTEMPT_VALUE_LIMIT = 200;

/** Блоки этапа 1, которые сообщают тьютору значение ответа. */
export const TUTOR_ATTEMPT_COMPONENTS: ReadonlySet<string> = new Set(['GuidedPractice', 'IndependentProblem']);

/** Пропсы для блока: onAttempt с привязкой к месту в уроке, или ничего. */
export function tutorAttemptProps(
  component: string,
  bridge: TutorBridge,
  blockIndex: number,
  stepIndex: number,
): { onAttempt?: (attempt: BlockAttempt) => void } {
  const report = bridge.onAttempt;
  if (!report || !TUTOR_ATTEMPT_COMPONENTS.has(component)) return {};
  return { onAttempt: (attempt) => report({ ...attempt, value: attempt.value.slice(0, ATTEMPT_VALUE_LIMIT), blockIndex, stepIndex }) };
}
