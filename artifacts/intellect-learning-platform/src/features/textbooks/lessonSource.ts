/** Подписи «откуда это в уроке»: учебник, параграф, страница. Данные — из lesson_metadata.textbook и content.source_ref. */

type SectionMeta = { number?: string | null; title?: string | null; page_from?: number | null; page_to?: number | null; role?: string };
export type LessonTextbookMeta = { title?: string | null; sections?: SectionMeta[] } | null | undefined;

const pages = (from?: number | null, to?: number | null) =>
  from == null ? '' : to == null || to === from ? `стр. ${from}` : `стр. ${from}–${to}`;

export function readLessonTextbook(metadata: Record<string, unknown> | null | undefined): LessonTextbookMeta {
  const value = metadata?.textbook;
  return value && typeof value === 'object' ? (value as LessonTextbookMeta) : null;
}

/** Основной параграф урока: «§ 12 Плотность вещества (стр. 45–49)». */
export function primarySectionLabel(textbook: LessonTextbookMeta): string | null {
  const primary = textbook?.sections?.find((section) => section.role !== 'supporting') ?? textbook?.sections?.[0];
  if (!primary) return null;
  const range = pages(primary.page_from, primary.page_to);
  return `${[primary.number, primary.title].filter(Boolean).join(' ')}${range ? ` (${range})` : ''}`;
}

/** Короткая ссылка для ученика: «§ 12, стр. 45–49» — без текста книги. */
export function studentTextbookRef(textbook: LessonTextbookMeta): string | null {
  const primary = textbook?.sections?.find((section) => section.role !== 'supporting') ?? textbook?.sections?.[0];
  if (!primary) return null;
  return [primary.number, pages(primary.page_from, primary.page_to)].filter(Boolean).join(', ') || null;
}

type SourceRef = { kind?: string; page?: number | null };

function refLabel(ref: SourceRef | undefined): string | null {
  if (!ref || typeof ref !== 'object') return null;
  const page = ref.page ? `, стр. ${ref.page}` : '';
  if (ref.kind === 'textbook') return `задача учебника${page}`;
  if (ref.kind === 'analog') return `аналог задачи учебника${page}`;
  if (ref.kind === 'section') return `по параграфу${page}`;
  return null;
}

/** Подпись блока в редакторе; у итоговой проверки — сколько вопросов опираются на учебник. */
export function blockSourceLabel(content: Record<string, unknown> | undefined): string | null {
  if (!content) return null;
  const own = refLabel(content.source_ref as SourceRef | undefined);
  if (own) return own;
  const questions = Array.isArray(content.questions) ? content.questions as Array<Record<string, unknown>> : [];
  const grounded = questions.filter((question) => refLabel(question?.source_ref as SourceRef | undefined)).length;
  return grounded ? `по учебнику: ${grounded} из ${questions.length} вопросов` : null;
}
