export type SampleQuestionData = { prompt: string; options: string[]; correct: number; explanation: string };
export type SampleAnswer = { choice: number; tries: number };
export type SampleLessonData = { id: string; subject: string; title: string; subtitle: string; hero: string; sceneNames: string[]; questions: Record<string, SampleQuestionData> };
export type SampleProgress = { version: 1; step: number; answers: Record<string, SampleAnswer> };
export const emptySample = (): SampleProgress => ({ version: 1, step: 0, answers: {} });
export function restoreSample(raw: string | null, lesson: SampleLessonData): SampleProgress {
  const result = emptySample();
  try {
    const data: unknown = JSON.parse(raw ?? 'null');
    if (!data || typeof data !== 'object') return result;
    const stored = data as Record<string, unknown>;
    if (stored.version !== 1) return result;
    if (Number.isInteger(stored.step) && Number(stored.step) >= 0 && Number(stored.step) < lesson.sceneNames.length) result.step = Number(stored.step);
    if (stored.answers && typeof stored.answers === 'object') for (const [id, value] of Object.entries(stored.answers)) {
      if (!value || typeof value !== 'object' || !Object.hasOwn(lesson.questions, id)) continue;
      const answer = value as Record<string, unknown>;
      if (typeof answer.choice === 'number' && Number.isInteger(answer.choice) && answer.choice >= 0 && answer.choice < lesson.questions[id].options.length && typeof answer.tries === 'number' && Number.isSafeInteger(answer.tries) && answer.tries > 0) result.answers[id] = { choice: answer.choice, tries: answer.tries };
    }
  } catch { /* A corrupt or unavailable local save must never prevent learning. */ }
  return result;
}
export function answerSample(state: SampleProgress, lesson: SampleLessonData, id: string, choice: number): SampleProgress {
  if (!Object.hasOwn(lesson.questions, id)) return state;
  const question = lesson.questions[id];
  if (!Number.isInteger(choice) || choice < 0 || choice >= question.options.length || state.answers[id]?.choice === question.correct) return state;
  return { ...state, answers: { ...state.answers, [id]: { choice, tries: (state.answers[id]?.tries ?? 0) + 1 } } };
}
