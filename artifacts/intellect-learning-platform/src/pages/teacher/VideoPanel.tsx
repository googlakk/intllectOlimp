import { useState } from 'react';
import { Loader2, PlayCircle, Trash2 } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { updateLessonBlocks, type Block, type GeneratedLesson } from '@/lib/api';
import { driveFileId } from '@/components/blocks/VideoLesson';

const EXPLANATION = new Set(['ShortExplanation', 'KeyConcept', 'WorkedExample', 'Presentation', 'Illustration', 'MindMap', 'Timeline']);

const partOf = (block: Block) => Number(block.content?.lesson_part) || 1;

// "1:20" or "80" -> seconds; empty -> undefined
function seconds(value: string): number | undefined {
  const text = value.trim();
  if (!text) return undefined;
  const [a, b] = text.split(':');
  const total = b === undefined ? Number(a) : Number(a) * 60 + Number(b);
  return Number.isFinite(total) && total >= 0 ? Math.round(total) : undefined;
}

// Put the video where explanation starts in that part, so it is an alternative to reading.
function insertVideo(blocks: Block[], video: Block, part: number): Block[] {
  let at = blocks.findIndex((b) => partOf(b) === part && EXPLANATION.has(b.component));
  if (at < 0) at = blocks.findIndex((b) => partOf(b) > part);
  if (at < 0) at = blocks.length;
  return [...blocks.slice(0, at), video, ...blocks.slice(at)];
}

export default function VideoPanel({ lesson, topicId }: { lesson: GeneratedLesson; topicId: number }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [summary, setSummary] = useState('');
  const [questions, setQuestions] = useState('');
  const [part, setPart] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const totalParts = lesson.total_parts ?? 1;
  const videos = lesson.blocks.map((block, index) => ({ block, index })).filter(({ block }) => block.component === 'VideoLesson');
  const objectiveIds = (lesson.lesson_metadata?.objectives ?? []).map((o) => o.id);

  const save = async (blocks: Block[]) => {
    setSaving(true);
    setError(null);
    try {
      await updateLessonBlocks(lesson.id, blocks);
      queryClient.invalidateQueries({ queryKey: ['lesson', topicId] });
      queryClient.invalidateQueries({ queryKey: ['lesson-status', topicId] });
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const add = async () => {
    if (!driveFileId(url)) {
      setError('Нужна ссылка на файл Google Drive: drive.google.com/file/d/…');
      return;
    }
    const video: Block = {
      component: 'VideoLesson',
      content: {
        title: title.trim() || 'Видеоурок',
        drive_url: url.trim(),
        start_sec: seconds(start),
        end_sec: seconds(end),
        summary: summary.split('\n').map((s) => s.trim()).filter(Boolean),
        questions: questions.split('\n').map((line) => line.trim()).filter(Boolean).map((line) => {
          const match = line.match(/^(\d{1,2}:\d{2})\s+(.+)$/);
          return match ? { time_label: match[1], question: match[2] } : { question: line };
        }),
        objective_ids: objectiveIds,
        evidence_stage: 'explanation',
        lesson_part: part,
      },
    };
    if (await save(insertVideo(lesson.blocks, video, part))) {
      setUrl(''); setTitle(''); setStart(''); setEnd(''); setSummary(''); setQuestions(''); setOpen(false);
    }
  };

  const remove = (index: number) => {
    if (confirm('Убрать видео из урока?')) save(lesson.blocks.filter((_, i) => i !== index));
  };

  const input = 'w-full rounded-xl border border-border bg-background px-3 py-2 text-sm';

  return (
    <div className="mb-6 rounded-2xl border border-border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-bold text-foreground"><PlayCircle className="w-5 h-5 text-primary" /> Видеоурок</div>
        {!open && (
          <button onClick={() => setOpen(true)} className="px-4 py-2 bg-primary/10 text-primary font-bold rounded-xl text-sm hover:bg-primary hover:text-primary-foreground transition-all">
            Добавить видео с Google Drive
          </button>
        )}
      </div>

      {videos.map(({ block, index }) => (
        <div key={index} className="flex items-center justify-between gap-3 text-sm">
          <span className="text-foreground font-medium">
            {String(block.content.title)}{totalParts > 1 ? ` · шаг ${partOf(block)}` : ''}
          </span>
          <button onClick={() => remove(index)} disabled={saving} className="text-destructive hover:opacity-70" title="Убрать">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}

      {open && (
        <div className="space-y-3">
          <input className={input} placeholder="Ссылка на видео в Google Drive" value={url} onChange={(e) => setUrl(e.target.value)} />
          <p className="text-xs text-muted-foreground">
            В Drive откройте у файла доступ «Все, у кого есть ссылка — читатель», иначе ученики увидят ошибку.
          </p>
          <input className={input} placeholder="Название (например: Площадь поверхности куба — объяснение)" value={title} onChange={(e) => setTitle(e.target.value)} />
          <div className="flex gap-3">
            <input className={input} placeholder="Начало фрагмента, 1:20" value={start} onChange={(e) => setStart(e.target.value)} />
            <input className={input} placeholder="Конец, 4:30" value={end} onChange={(e) => setEnd(e.target.value)} />
            {totalParts > 1 && (
              <select className={input} value={part} onChange={(e) => setPart(Number(e.target.value))}>
                {Array.from({ length: totalParts }, (_, i) => <option key={i} value={i + 1}>Шаг {i + 1}</option>)}
              </select>
            )}
          </div>
          <textarea className={input} rows={3} placeholder="Главное из видео — по пункту в строке" value={summary} onChange={(e) => setSummary(e.target.value)} />
          <textarea className={input} rows={3} placeholder={'Вопросы по ходу просмотра — по одному в строке, можно со временем:\n1:20 Почему площадь грани равна a²?'} value={questions} onChange={(e) => setQuestions(e.target.value)} />
          {error && <p className="text-sm font-bold text-destructive">{error}</p>}
          <p className="text-xs text-muted-foreground">После сохранения урок станет черновиком — его нужно будет опубликовать снова.</p>
          <div className="flex gap-3 justify-end">
            <button onClick={() => { setOpen(false); setError(null); }} className="px-4 py-2 rounded-xl text-sm font-bold text-muted-foreground hover:bg-muted">Отмена</button>
            <button onClick={add} disabled={saving} className="px-4 py-2 rounded-xl text-sm font-bold bg-primary text-primary-foreground flex items-center gap-2 disabled:opacity-60">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />} Сохранить
            </button>
          </div>
        </div>
      )}
      {!open && error && <p className="text-sm font-bold text-destructive">{error}</p>}
    </div>
  );
}
