import { useQuery } from '@tanstack/react-query';

import { request } from './client';

export type TutorEvent = 'answer_submitted' | 'hint_requested' | 'idle' | 'message';
export type TutorOutcome = 'correct' | 'incorrect' | 'wrong_unit';

export type TutorTurnInput = {
  topic_id: number;
  block_index: number;
  question_index?: number | null;
  step_index?: number | null;
  event: TutorEvent;
  message?: string | null;
  student_value?: string | null;
  client_outcome?: TutorOutcome | null;
};

/** Команда тьютора уроку: open_theory — только назад, к объяснению (target_block_index — исходный индекс). */
export type TutorAction = { type: 'show_hint' | 'open_theory' | 'call_teacher'; target_block_index?: number };

export type TutorTurnResponse = {
  turn_id: number | null;
  reply: string;
  source: 'template' | 'hint' | 'llm' | 'fallback' | 'guard' | 'silent';
  action: TutorAction | null;
  offer: boolean;
  outcome: TutorOutcome | null;
  assessment_mode: boolean;
  hint_level: number | null;
};

export type TutorSessionTurn = {
  id: number;
  block_index: number;
  question_index: number | null;
  event: TutorEvent;
  student_text: string | null;
  reply: string;
  source: TutorTurnResponse['source'];
  hint_level: number | null;
};

export type TutorSession = { enabled: boolean; turns: TutorSessionTurn[] };

export const postTutorTurn = (input: TutorTurnInput) =>
  request<TutorTurnResponse>('/tutor/turn', { method: 'POST', body: JSON.stringify(input) });

export const getTutorSession = (topicId: number) => request<TutorSession>(`/tutor/session?topic_id=${topicId}`);

/** Диалог по уроку. Помощник выключен или недоступен — просто { enabled: false }, урок идёт как обычно. */
export const useTutorSession = (topicId: number, studentId: number | undefined, enabled: boolean) =>
  useQuery({
    // Ключ с учеником: на общем школьном компьютере следующий ученик не увидит чужой диалог.
    queryKey: ['tutor-session', studentId, topicId],
    queryFn: () => getTutorSession(topicId),
    enabled: enabled && topicId > 0 && Boolean(studentId),
    retry: false,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });
