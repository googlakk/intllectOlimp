/**
 * Окно отзыва показываем один раз на урок (тему и версию): повторный заход в пройденный урок
 * или обновление страницы не должны снова спрашивать. Память — в браузере ученика; нет доступа
 * к хранилищу (приватный режим) — просто спросим ещё раз.
 */
const key = (topicId: number, versionId: number | null | undefined) => `lesson-feedback:${topicId}:${versionId ?? 'latest'}`;

export function feedbackAlreadyAsked(topicId: number, versionId: number | null | undefined): boolean {
  try {
    return window.localStorage.getItem(key(topicId, versionId)) !== null;
  } catch {
    return false;
  }
}

export function rememberFeedbackAsked(topicId: number, versionId: number | null | undefined): void {
  try {
    window.localStorage.setItem(key(topicId, versionId), new Date().toISOString());
  } catch {
    /* Хранилище недоступно — не страшно. */
  }
}

/** Отзыв считается заполненным, если есть хоть что-то: оценка, ответ про ошибки или текст. */
export function hasFeedback(rating: number | null, hadErrors: boolean | null, comment: string): boolean {
  return rating !== null || hadErrors !== null || comment.trim().length > 0;
}
