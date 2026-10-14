import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import type { ClassroomStudent } from '@/lib/api';

export function StudentRemovalDialog({ student, classroomName, onClose, onDelete }: {
  student: ClassroomStudent; classroomName: string; onClose: () => void; onDelete: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  return <Dialog open onOpenChange={open => { if (!open && !busy) onClose(); }}>
    <DialogContent onEscapeKeyDown={event => { if (busy) event.preventDefault(); }} onPointerDownOutside={event => { if (busy) event.preventDefault(); }}>
      <DialogTitle>Удалить ученика</DialogTitle>
      <DialogDescription>Аккаунт будет убран из класса, вход по этому логину станет недоступен. История обучения сохранится. Вернуть аккаунт можно в разделе «Удалённые ученики».</DialogDescription>
      <div className="rounded-md border bg-muted/30 p-3 text-sm">
        <p className="font-semibold">{student.name}</p>
        <p className="mt-1 break-all font-mono">{student.login}</p>
        <p className="mt-1 text-muted-foreground">Класс: {classroomName}</p>
      </div>
      <p className="text-sm">Другие аккаунты, в том числе с таким же именем, останутся без изменений.</p>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <div className="flex flex-wrap justify-end gap-2">
        <button disabled={busy} onClick={onClose} className="h-11 rounded-md border px-4">Отмена</button>
        <button disabled={busy} onClick={async () => {
          setBusy(true); setError('');
          try { await onDelete(); }
          catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось удалить ученика.'); }
          finally { setBusy(false); }
        }} className="h-11 rounded-md bg-destructive px-4 font-semibold text-destructive-foreground">{busy ? 'Удаляем…' : 'Удалить аккаунт'}</button>
      </div>
    </DialogContent>
  </Dialog>;
}
