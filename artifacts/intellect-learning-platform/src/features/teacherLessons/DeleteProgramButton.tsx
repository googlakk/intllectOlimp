import { Loader2, Trash2 } from 'lucide-react';
import { useDeleteSubject, type Subject } from '@/lib/api';

export function DeleteProgramButton({ subject, onDeleted }: { subject: Subject; onDeleted: (subjectId: number) => void }) {
  const deletion = useDeleteSubject();
  const remove = async () => {
    if (!window.confirm(`Удалить КТП «${subject.name}» (${subject.grade} класс)?\n\nБудут удалены программа, разделы и все её уроки. Учебники сохранятся. Если у учеников есть результаты по этой программе, удаление будет запрещено. Это действие нельзя отменить.`)) return;
    try {
      await deletion.mutateAsync(subject.id);
      onDeleted(subject.id);
    } catch { /* Ошибка сервера показана рядом с кнопкой. */ }
  };

  return (
    <>
      <button type="button" onClick={() => void remove()} disabled={deletion.isPending}
        className="inline-flex h-11 items-center gap-2 rounded-lg border border-destructive/30 bg-card px-3 text-sm font-semibold text-destructive hover:bg-destructive/10 disabled:opacity-50">
        {deletion.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
        {deletion.isPending ? 'Удаляется…' : 'Удалить КТП'}
      </button>
      {deletion.error && <p role="alert" className="basis-full text-sm text-destructive">{deletion.error.message}</p>}
    </>
  );
}
