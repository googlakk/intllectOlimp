import type { Textbook } from '@/lib/api/textbooks';

export type StatusView = { label: string; tone: 'muted' | 'progress' | 'ok' | 'warn' | 'error'; canRun: boolean };

/** Статус книги для учителя: что происходит и можно ли запустить обработку снова. */
export function textbookStatusView(book: Pick<Textbook, 'status' | 'stalled' | 'progress'>): StatusView {
  if (book.stalled) return { label: 'Обработка остановилась — запустите снова', tone: 'warn', canRun: true };
  const { progress } = book;
  switch (book.status) {
    case 'uploaded': return { label: 'Загружен, ждёт обработки', tone: 'muted', canRun: true };
    case 'extracting': return { label: 'Извлекаем текст страниц…', tone: 'progress', canRun: false };
    case 'needs_ai': return {
      label: progress.scans_left ? `Текст извлечён; ${progress.scans_left} стр. — сканы, нужно распознавание ИИ` : 'Текст извлечён; для оглавления и заданий нужен ИИ',
      tone: 'warn', canRun: true,
    };
    case 'recognizing': return { label: `Распознаём сканы… осталось ${progress.scans_left ?? '?'} стр.`, tone: 'progress', canRun: false };
    case 'structuring': return {
      label: progress.items_left !== undefined ? `Разбираем параграфы… осталось ${progress.items_left}` : 'Разбираем оглавление…',
      tone: 'progress', canRun: false,
    };
    case 'ready': return { label: 'Готов', tone: 'ok', canRun: true };
    case 'needs_review': return { label: 'Готов, но нужна проверка', tone: 'warn', canRun: true };
    case 'failed': return { label: 'Ошибка обработки', tone: 'error', canRun: true };
    default: return { label: book.status, tone: 'muted', canRun: false };
  }
}

export const ITEM_KIND_LABELS: Record<string, string> = {
  definition: 'Определение', formula: 'Формула', example: 'Пример', question: 'Вопрос',
  exercise: 'Задача', experiment: 'Опыт', fact: 'Факт',
};
