export const sceneNames = ['Замысел', 'Построить', 'Открытие', 'Лаборатория', 'Предсказать', 'Найти ошибку', 'Твой проект', 'Итоги'];
export const questions = {
  predict: { answer: 5, prompt: 'Площадь сада — 25 м². Какой длины будет его сторона?', options: [5, 12.5, 25], unit: 'м', explanation: 'Нужны два одинаковых множителя: 5 × 5 = 25. Поэтому √25 = 5, а сторона равна 5 м.' },
  trap: { answer: 4, prompt: 'Друг говорит: «√16 = 8, ведь 16 : 2 = 8». Какой ответ верный?', options: [4, 8, -4], unit: '', explanation: 'Корень не делит число пополам. 8 × 8 = 64, а 4 × 4 = 16. Число −4 тоже даёт 16 в квадрате, но знак √ обозначает неотрицательный корень: √16 = 4.' },
  project: { answer: 7, prompt: 'Для квадратной площадки выделили 49 м². Какую длину стороны указать на чертеже?', options: [], unit: 'м', explanation: '7 × 7 = 49. Значит, √49 = 7, и сторона площадки равна 7 м. Проверка вернула нас к исходной площади.' },
} as const;
export type QuestionId = keyof typeof questions;
export type Response = { value: number; tries: number; correct: boolean };
export function answerFeedback(id: QuestionId, response: Response): string {
  if (response.correct) return questions[id].explanation;
  if (response.value < 0 && response.value ** 2 === questions[id].answer ** 2) {
    return id === 'trap' ? 'Верно, (−4)² = 16. Но арифметический квадратный корень неотрицателен. Какое другое число подойдёт?' : 'Квадрат этого числа даёт нужную площадь. Но длина стороны не может быть отрицательной. Возьми положительное число с таким же квадратом.';
  }
  return `${response.value.toLocaleString('ru')} × ${response.value.toLocaleString('ru')} = ${(response.value ** 2).toLocaleString('ru')}. Нужно получить ${questions[id].answer ** 2}. Попробуй другое число.`;
}
export type GardenState = { version: 1; step: number; side: number; responses: Partial<Record<QuestionId, Response>> };
export const initialState = (): GardenState => ({ version: 1, step: 0, side: 3, responses: {} });
export function recordAnswer(state: GardenState, id: QuestionId, value: number): GardenState {
  if (!Number.isFinite(value) || state.responses[id]?.correct) return state;
  return { ...state, responses: { ...state.responses, [id]: { value, tries: (state.responses[id]?.tries ?? 0) + 1, correct: value === questions[id].answer } } };
}
export function restoreState(raw: string | null): GardenState {
  try {
    const data: unknown = JSON.parse(raw ?? 'null');
    if (!data || typeof data !== 'object' || !('version' in data) || data.version !== 1) return initialState();
    const state = data as Record<string, unknown>;
    const restored = initialState();
    if (typeof state.step === 'number' && Number.isInteger(state.step) && state.step >= 0 && state.step < sceneNames.length) restored.step = state.step;
    if (typeof state.side === 'number' && Number.isInteger(state.side) && state.side >= 1 && state.side <= 8) restored.side = state.side;
    if (state.responses && typeof state.responses === 'object') {
      for (const id of Object.keys(questions) as QuestionId[]) {
        const r: unknown = (state.responses as Record<string, unknown>)[id];
        if (!r || typeof r !== 'object') continue;
        const response = r as Record<string, unknown>;
        if (typeof response.value === 'number' && Number.isFinite(response.value) && typeof response.tries === 'number' && Number.isInteger(response.tries) && response.tries > 0) {
          restored.responses[id] = { value: response.value, tries: response.tries, correct: response.value === questions[id].answer };
        }
      }
    }
    return restored;
  } catch { return initialState(); }
}
