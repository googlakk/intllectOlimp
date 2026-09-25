import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, RotateCw } from 'lucide-react';
import { processTextbook, updateTextbookPage, useTextbook, useTextbookSection, type TextbookPageView } from '@/lib/api';
import { parseMathText } from '@/components/blocks/ShortExplanation';
import { ITEM_KIND_LABELS, textbookStatusView } from './textbookStatus';

const TONES = {
  muted: 'bg-muted text-muted-foreground', progress: 'bg-primary/10 text-primary', ok: 'bg-emerald-100 text-emerald-800',
  warn: 'bg-amber-100 text-amber-900', error: 'bg-destructive/10 text-destructive',
};

export function StatusBadge({ book }: { book: Parameters<typeof textbookStatusView>[0] }) {
  const view = textbookStatusView(book);
  return <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-semibold ${TONES[view.tone]}`}>{view.label}</span>;
}

/** Книга: статус обработки, параграфы и страницы, которые стоит проверить. */
export function TextbookDetailView({ id, onBack }: { id: number; onBack: () => void }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useTextbook(id);
  const [sectionId, setSectionId] = useState<number | null>(null);
  const [runError, setRunError] = useState('');

  if (isLoading) return <p>Загружаем учебник…</p>;
  if (isError || !data) return <p role="alert">Не удалось загрузить учебник.</p>;
  const { textbook, sections, pages_to_review: review } = data;
  const status = textbookStatusView(textbook);

  const run = async () => {
    setRunError('');
    try {
      await processTextbook(textbook.id);
      await queryClient.invalidateQueries({ queryKey: ['textbook', id] });
      await queryClient.invalidateQueries({ queryKey: ['textbooks'] });
    } catch (reason) {
      setRunError(reason instanceof Error ? reason.message : 'Не удалось запустить обработку');
    }
  };

  if (sectionId !== null) return <SectionView textbookId={id} sectionId={sectionId} onBack={() => setSectionId(null)} />;

  return (
    <section className="space-y-4">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1 text-sm font-semibold text-primary"><ArrowLeft className="h-4 w-4" /> Все учебники</button>
      <div className="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-border bg-card p-5">
        <div className="space-y-2">
          <h2 className="text-xl font-bold">{textbook.title}</h2>
          <p className="text-sm text-muted-foreground">{textbook.grade} класс · {textbook.language === 'ky' ? 'кыргызский' : 'русский'}{textbook.page_count ? ` · ${textbook.page_count} стр.` : ''}</p>
          <StatusBadge book={textbook} />
          {textbook.error && <p className="text-sm text-destructive">{textbook.error}</p>}
          {textbook.progress.calibration !== undefined && textbook.progress.calibration < 0.3 && (
            <p className="text-sm text-amber-900">Страницы оглавления плохо совпали с PDF — проверьте диапазоны параграфов.</p>
          )}
        </div>
        {status.canRun && (
          <button type="button" onClick={run} className="inline-flex min-h-[44px] items-center gap-2 rounded-xl border border-border px-4 text-sm font-semibold hover:bg-muted">
            <RotateCw className="h-4 w-4" aria-hidden /> Запустить обработку
          </button>
        )}
        {runError && <p role="alert" className="w-full text-sm text-destructive">{runError}</p>}
      </div>

      {review.length > 0 && (
        <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          Проверьте распознавание на {review.length} стр. (PDF: {review.slice(0, 12).map((index) => index + 1).join(', ')}{review.length > 12 ? '…' : ''}) — там формулы или фрагменты прочитаны неуверенно.
        </p>
      )}

      {sections.length > 0 ? (
        <div className="overflow-x-auto rounded-2xl border border-border bg-card">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted-foreground">
              <tr><th className="px-4 py-2">Параграф</th><th className="px-2">Страницы</th><th className="px-2">Элементы</th><th /></tr>
            </thead>
            <tbody>
              {sections.map((section) => (
                <tr key={section.id} className="border-t border-border">
                  <td className="px-4 py-2">
                    {section.chapter && <span className="block text-xs text-muted-foreground">{section.chapter}</span>}
                    {section.number} {section.title}
                  </td>
                  <td className="px-2">с. {section.printed_page ?? '—'}</td>
                  <td className="px-2">{section.items_status === 'done' ? section.items : section.items_status === 'failed' ? 'ошибка' : '…'}</td>
                  <td className="px-2"><button type="button" onClick={() => setSectionId(section.id)} className="font-semibold text-primary">Открыть</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Параграфы появятся после разбора оглавления.</p>
      )}
    </section>
  );
}

function SectionView({ textbookId, sectionId, onBack }: { textbookId: number; sectionId: number; onBack: () => void }) {
  const { data, isLoading, isError } = useTextbookSection(textbookId, sectionId);
  if (isLoading) return <p>Загружаем параграф…</p>;
  if (isError || !data) return <p role="alert">Не удалось загрузить параграф.</p>;
  const { section, pages, items } = data;
  return (
    <section className="space-y-4">
      <button type="button" onClick={onBack} className="inline-flex items-center gap-1 text-sm font-semibold text-primary"><ArrowLeft className="h-4 w-4" /> К параграфам</button>
      <h2 className="text-xl font-bold">{section.number} {section.title}</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          <h3 className="font-semibold">Элементы ({items.length})</h3>
          {items.length === 0 && <p className="text-sm text-muted-foreground">Элементы ещё не выделены.</p>}
          <ol className="space-y-2">
            {items.map((item) => (
              <li key={item.id} className="rounded-xl border border-border bg-card p-3 text-sm">
                <p className="mb-1 text-xs font-semibold text-muted-foreground">
                  {ITEM_KIND_LABELS[item.kind] ?? item.kind}{item.label ? ` · ${item.label}` : ''}{item.page ? ` · стр. ${item.page}` : ''}
                  {item.difficulty ? ` · сложность ${item.difficulty}` : ''}
                </p>
                <div>{parseMathText(item.text)}</div>
                {item.answer && <p className="mt-1 text-xs text-muted-foreground">Ответ: {parseMathText(item.answer)}</p>}
              </li>
            ))}
          </ol>
        </div>
        <div className="space-y-3">
          <h3 className="font-semibold">Текст страниц</h3>
          {pages.map((page) => <PageEditor key={page.page_index} textbookId={textbookId} page={page} />)}
        </div>
      </div>
    </section>
  );
}

function PageEditor({ textbookId, page }: { textbookId: number; page: TextbookPageView }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(page.text);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      await updateTextbookPage(textbookId, page.page_index, text);
      setEditing(false);
      await queryClient.invalidateQueries({ queryKey: ['textbook-section', textbookId] });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Не удалось сохранить');
    } finally {
      setSaving(false);
    }
  };

  const source = page.source === 'ocr' ? 'распознано ИИ' : page.source === 'edited' ? 'исправлено' : 'текст PDF';
  return (
    <article className={`rounded-xl border bg-card p-3 text-sm ${page.needs_review ? 'border-amber-400' : 'border-border'}`}>
      <div className="mb-2 flex items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>стр. {page.printed_page} · {source}{page.needs_review ? ' · проверить' : ''}</span>
        {!editing && <button type="button" onClick={() => setEditing(true)} className="font-semibold text-primary">Исправить</button>}
      </div>
      {page.uncertain.length > 0 && <p className="mb-2 text-xs text-amber-900">Неуверенно: {page.uncertain.join('; ')}</p>}
      {editing ? (
        <div className="space-y-2">
          <textarea value={text} onChange={(event) => setText(event.target.value)} rows={14}
            className="w-full rounded-lg border border-border bg-background p-2 font-mono text-xs" aria-label={`Текст страницы ${page.printed_page}`} />
          {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
          <div className="flex gap-2">
            <button type="button" onClick={save} disabled={saving} className="min-h-[40px] rounded-lg bg-primary px-4 text-xs font-semibold text-primary-foreground disabled:opacity-50">Сохранить</button>
            <button type="button" onClick={() => { setEditing(false); setText(page.text); }} className="min-h-[40px] rounded-lg border border-border px-4 text-xs font-semibold">Отмена</button>
          </div>
        </div>
      ) : (
        <div className="max-h-72 overflow-y-auto whitespace-pre-wrap leading-relaxed">
          {/* Текст книги — как есть: разметка исказила бы «1.», «-», «_». Формулы — только в распознанном тексте с $. */}
          {!page.text ? <span className="text-muted-foreground">Текста нет</span> : page.text.includes('$') ? parseMathText(page.text) : page.text}
        </div>
      )}
    </article>
  );
}
