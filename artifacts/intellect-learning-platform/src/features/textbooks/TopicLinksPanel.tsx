import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Check, Sparkles, X } from 'lucide-react';
import { confirmSuggestedLinks, setTopicTextbookLinks, suggestTextbookLinks, useTextbookLinks } from '@/lib/api';
import { linkSummary, topicLinkState, type LinkState } from './linkState';

const STATE_LABELS: Record<LinkState, string> = {
  confirmed: 'подтверждено', suggested: 'предложено', covered: 'по пройденным темам', rejected: 'параграф не нужен', none: 'не найдено',
};
const STATE_TONES: Record<LinkState, string> = {
  confirmed: 'bg-emerald-100 text-emerald-800', suggested: 'bg-amber-100 text-amber-900',
  covered: 'bg-muted text-muted-foreground', rejected: 'bg-muted text-muted-foreground', none: 'bg-destructive/10 text-destructive',
};

/** Привязка тем КТП к параграфам: в генерацию уроков идут только подтверждённые связи. */
export function TopicLinksPanel({ textbookId, hasSubject, hasSections }: { textbookId: number; hasSubject: boolean; hasSections: boolean }) {
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useTextbookLinks(textbookId, hasSubject);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [selected, setSelected] = useState<ReadonlySet<number>>(new Set());

  if (!hasSubject) return <p className="text-sm text-muted-foreground">Укажите для учебника предмет из КТП — тогда темы можно привязать к параграфам.</p>;
  if (isLoading) return <p>Загружаем темы…</p>;
  if (isError || !data) return <p role="alert">{error instanceof Error ? error.message : 'Не удалось загрузить темы.'}</p>;

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['textbook-links', textbookId] });
  const act = async (action: () => Promise<unknown>) => {
    setBusy(true);
    setMessage('');
    try {
      await action();
      await refresh();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : 'Не удалось сохранить');
    } finally {
      setBusy(false);
    }
  };
  const suggest = () => act(async () => {
    const counts = await suggestTextbookLinks(textbookId);
    setMessage(`Подобрано: по ссылке из КТП — ${counts.confirmed}, предложено — ${counts.suggested}, не найдено — ${counts.not_found}.`);
  });

  const summary = linkSummary(data.topics);
  const suggestedIds = data.topics.filter((topic) => topicLinkState(topic) === 'suggested').map((topic) => topic.id);
  const chosen = suggestedIds.filter((topicId) => selected.has(topicId));
  const allChosen = suggestedIds.length > 0 && chosen.length === suggestedIds.length;
  const toggle = (topicId: number) => setSelected((current) => {
    const next = new Set(current);
    if (next.has(topicId)) next.delete(topicId); else next.add(topicId);
    return next;
  });
  const confirmChosen = () => act(async () => {
    const result = await confirmSuggestedLinks(textbookId, chosen);
    setSelected(new Set());
    setMessage(`Подтверждено тем: ${result.topics}.`);
  });
  const topics = onlyMissing ? data.topics.filter((topic) => topicLinkState(topic) === 'suggested' || topicLinkState(topic) === 'none') : data.topics;
  return (
    <section className="space-y-3" aria-label="Темы КТП и параграфы">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          Подтверждено {summary.confirmed} · предложено {summary.suggested} · не найдено {summary.none} · по пройденным темам {summary.covered}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={onlyMissing} onChange={(event) => setOnlyMissing(event.target.checked)} /> Только без учебника</label>
          <button type="button" onClick={suggest} disabled={busy || !hasSections}
            className="inline-flex min-h-[44px] items-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground disabled:opacity-50">
            <Sparkles className="h-4 w-4" aria-hidden /> Подобрать параграфы
          </button>
        </div>
      </div>
      {message && <p role="status" className="text-sm">{message}</p>}
      <p className="text-xs text-muted-foreground">Уроки строятся только по подтверждённым параграфам. Предложения не затирают уже сделанный выбор.</p>
      {suggestedIds.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm">
          <label className="flex items-center gap-2 font-semibold">
            <input type="checkbox" checked={allChosen} onChange={() => setSelected(allChosen ? new Set() : new Set(suggestedIds))} />
            Выбрать все предложенные ({suggestedIds.length})
          </label>
          <span className="text-muted-foreground">Снимите галочки у тем, где предложение не подходит.</span>
          <button type="button" onClick={confirmChosen} disabled={busy || chosen.length === 0}
            className="ml-auto inline-flex min-h-[40px] items-center gap-1 rounded-lg bg-emerald-600 px-4 text-sm font-semibold text-white disabled:opacity-50">
            <Check className="h-4 w-4" aria-hidden /> Подтвердить выбранные ({chosen.length})
          </button>
        </div>
      )}
      <div className="overflow-x-auto rounded-2xl border border-border bg-card">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-muted-foreground">
            <tr><th className="w-10 px-3 py-2"><span className="sr-only">Выбор</span></th><th className="px-2 py-2">Тема КТП</th><th className="px-2">Учебник</th><th className="px-2">Действия</th></tr>
          </thead>
          <tbody>
            {topics.map((topic) => {
              const state = topicLinkState(topic);
              return (
                <tr key={topic.id} className="border-t border-border align-top">
                  <td className="px-3 py-2">
                    {state === 'suggested' && (
                      <input type="checkbox" checked={selected.has(topic.id)} onChange={() => toggle(topic.id)}
                        aria-label={`Выбрать тему ${topic.name}`} className="h-4 w-4" />
                    )}
                  </td>
                  <td className="px-2 py-2">{topic.ktp_number ? `${topic.ktp_number}. ` : ''}{topic.name}</td>
                  <td className="px-2 py-2">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${STATE_TONES[state]}`}>{STATE_LABELS[state]}</span>
                    {topic.links.map((link) => (
                      <span key={link.section_id} className="mt-1 block text-xs">
                        {link.number} {link.title}{link.source === 'ktp' ? ' (из КТП)' : ''}
                      </span>
                    ))}
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      {state === 'suggested' && (
                        <button type="button" disabled={busy} onClick={() => act(() => setTopicTextbookLinks(textbookId, topic.id, topic.links.map((link) => link.section_id)))}
                          className="inline-flex min-h-[36px] items-center gap-1 rounded-lg bg-emerald-600 px-3 text-xs font-semibold text-white disabled:opacity-50">
                          <Check className="h-3.5 w-3.5" aria-hidden /> Подтвердить
                        </button>
                      )}
                      <select aria-label={`Выбрать параграф для темы ${topic.name}`} value="" disabled={busy}
                        onChange={(event) => { const id = Number(event.target.value); if (id) void act(() => setTopicTextbookLinks(textbookId, topic.id, [id])); }}
                        className="min-h-[36px] max-w-[220px] rounded-lg border border-border bg-background px-2 text-xs">
                        <option value="">Выбрать параграф…</option>
                        {data.sections.map((section) => <option key={section.id} value={section.id}>{section.number} {section.title}</option>)}
                      </select>
                      {topic.links.length > 0 && (
                        <button type="button" disabled={busy} aria-label={`Снять привязку темы ${topic.name}`}
                          onClick={() => act(() => setTopicTextbookLinks(textbookId, topic.id, []))}
                          className="grid h-9 w-9 place-items-center rounded-lg border border-border text-muted-foreground hover:bg-muted disabled:opacity-50">
                          <X className="h-4 w-4" aria-hidden />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
