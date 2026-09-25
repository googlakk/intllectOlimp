import { useState, type FormEvent } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Upload } from 'lucide-react';
import { MAX_TEXTBOOK_BYTES, createTextbook, deleteUnuploadedTextbook, processTextbook, uploadTextbookFile, useSubjects } from '@/lib/api';

const GRADES = [5, 6, 7, 8, 9, 10, 11];

/** Загрузка учебника: запись в базе → файл прямо в хранилище → запуск обработки. */
export function TextbookUpload({ onDone }: { onDone: (id: number) => void }) {
  const queryClient = useQueryClient();
  const { data: subjects } = useSubjects();
  const [title, setTitle] = useState('');
  const [grade, setGrade] = useState(8);
  const [subjectId, setSubjectId] = useState<number | ''>('');
  const [language, setLanguage] = useState<'ru' | 'ky'>('ru');
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState('');
  const gradeSubjects = (subjects ?? []).filter((subject) => subject.grade === grade);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !title.trim()) return;
    if (file.size > MAX_TEXTBOOK_BYTES) {
      setError('Файл больше 150 МБ');
      return;
    }
    setError('');
    setProgress(0);
    let textbookId: number | null = null;
    try {
      const { textbook, upload_url } = await createTextbook({
        title: title.trim(), grade, subject_id: subjectId || null, language, file_name: file.name, file_size: file.size,
      });
      textbookId = textbook.id;
      await uploadTextbookFile(upload_url, file, setProgress);
    } catch (reason) {
      // Файл не дошёл до хранилища — убираем пустую запись, чтобы не копились «загруженные» книги без файла.
      if (textbookId !== null) await deleteUnuploadedTextbook(textbookId);
      setProgress(null);
      setError(reason instanceof Error ? reason.message : 'Не удалось загрузить учебник');
      return;
    }
    // Файл уже в хранилище: если запуск обработки не удался, его можно повторить в карточке книги.
    await processTextbook(textbookId).catch(() => undefined);
    await queryClient.invalidateQueries({ queryKey: ['textbooks'] });
    setTitle(''); setFile(null); setProgress(null);
    onDone(textbookId);
  };

  const busy = progress !== null;
  const field = 'mt-1 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm';
  return (
    <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
      <h2 className="flex items-center gap-2 text-lg font-bold"><Upload className="h-5 w-5 text-primary" aria-hidden /> Загрузить учебник</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-semibold sm:col-span-2">Название
          <input className={field} value={title} onChange={(event) => setTitle(event.target.value)} maxLength={300} required placeholder="Физика. 8 класс" />
        </label>
        <label className="text-sm font-semibold">Класс
          <select className={field} value={grade} onChange={(event) => { setGrade(Number(event.target.value)); setSubjectId(''); }}>
            {GRADES.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label className="text-sm font-semibold">Язык учебника
          <select className={field} value={language} onChange={(event) => setLanguage(event.target.value as 'ru' | 'ky')}>
            <option value="ru">Русский</option>
            <option value="ky">Кыргызский</option>
          </select>
        </label>
        <label className="text-sm font-semibold sm:col-span-2">Предмет из КТП
          <select className={field} value={subjectId} onChange={(event) => setSubjectId(event.target.value ? Number(event.target.value) : '')}>
            <option value="">— не выбран —</option>
            {gradeSubjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name}</option>)}
          </select>
        </label>
        <label className="text-sm font-semibold sm:col-span-2">Файл PDF (до 150 МБ)
          <input className={field} type="file" accept="application/pdf,.pdf" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
        </label>
      </div>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {busy && (
        <div className="space-y-1" aria-live="polite">
          <div className="h-2 overflow-hidden rounded-full bg-muted"><div className="h-full bg-primary transition-all" style={{ width: `${Math.round((progress ?? 0) * 100)}%` }} /></div>
          <p className="text-xs text-muted-foreground">Загружаем файл… {Math.round((progress ?? 0) * 100)}%</p>
        </div>
      )}
      <button type="submit" disabled={busy || !file || !title.trim()}
        className="min-h-[44px] rounded-xl bg-primary px-5 font-semibold text-primary-foreground disabled:opacity-50">
        Загрузить и обработать
      </button>
      <p className="text-xs text-muted-foreground">Файл хранится закрыто: ученики не видят текст учебника, только ссылки на страницы.</p>
    </form>
  );
}
