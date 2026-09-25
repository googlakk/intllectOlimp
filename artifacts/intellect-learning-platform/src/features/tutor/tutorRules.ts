import type { Block } from '@/lib/api/types';
import type { TutorAction, TutorSessionTurn } from '@/lib/api/tutor';
import { canNavigateToStep } from '@/features/lessons/lessonNavigation';
import type { TutorAttempt } from './tutorBridge';

export type TutorMessage = {
  id: string;
  role: 'student' | 'tutor';
  text: string;
  blockIndex: number;
  /** Позиция в маршруте, куда ведёт кнопка «Вернуться к объяснению». */
  theoryStep?: number | null;
  offer?: boolean;
};

/** Итоговое задание: тьютор молчит (зеркало assessment_mode на сервере). */
export function isTutorLocked(block: Block | undefined): boolean {
  if (!block) return false;
  const content = (block.content ?? {}) as Record<string, unknown>;
  return block.component === 'MasteryCheck' || content.evidence_stage === 'assessment';
}

/**
 * Куда тьютор может увести урок: только назад, к уже открытому шагу маршрута.
 * Сервер присылает исходный индекс блока; маршрут может его не содержать.
 */
export function resolveTheoryStep(
  action: TutorAction | null | undefined,
  activeOriginalIndices: number[],
  currentStep: number,
  maxOpenedStep: number,
): number | null {
  if (action?.type !== 'open_theory' || typeof action.target_block_index !== 'number') return null;
  const step = activeOriginalIndices.indexOf(action.target_block_index);
  if (step < 0 || step >= currentStep || !canNavigateToStep(step, maxOpenedStep)) return null;
  return step;
}

/** Та же попытка ещё раз (двойное нажатие «Проверить») — не новая ошибка для тьютора. */
export function isRepeatAttempt(previous: TutorAttempt | null, next: TutorAttempt): boolean {
  return Boolean(previous)
    && previous!.blockIndex === next.blockIndex
    && previous!.value === next.value
    && previous!.outcome === next.outcome;
}

/** Диалог после перезагрузки страницы: реплики ученика и тьютора по порядку. */
export function sessionToMessages(turns: TutorSessionTurn[]): TutorMessage[] {
  return turns.flatMap((turn) => [
    ...(turn.student_text ? [{ id: `s${turn.id}`, role: 'student' as const, text: turn.student_text, blockIndex: turn.block_index }] : []),
    ...(turn.reply ? [{ id: `t${turn.id}`, role: 'tutor' as const, text: turn.reply, blockIndex: turn.block_index }] : []),
  ]);
}

const IDLE_TEASERS = ['Застрял? Спроси меня', 'Могу дать подсказку', 'Разберём задачу по шагам?', 'Непонятно условие? Напиши мне'];
const LOCKED_TEASERS = ['Итоговое задание — здесь ты справляешься сам', 'Если что-то забыл, вернись к объяснению'];

/** Что плашка помощника показывает в покое: предложение помощи важнее дежурных фраз. */
export function tutorTeasers({ locked, hasOffer, lastReply }: { locked: boolean; hasOffer: boolean; lastReply?: string }): string[] {
  if (locked) return LOCKED_TEASERS;
  if (hasOffer && lastReply) return [lastReply];
  return IDLE_TEASERS;
}
