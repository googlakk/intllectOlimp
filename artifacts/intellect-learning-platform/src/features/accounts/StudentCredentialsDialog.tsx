import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { PasswordChoice } from './PasswordChoice';
import { parseStudentCsv, type StudentCsvRow } from './studentCsv';

export function StudentCredentialsDialog({ mode, names, count, onClose, onSubmit }: {
  mode: 'create' | 'reset'; names?: string; count?: number;
  onClose: () => void; onSubmit: (rows: StudentCsvRow[], password?: string, onProgress?: (completed: number, total: number) => void) => Promise<void>;
}) {
  const [source, setSource] = useState(names || '');
  const [manual, setManual] = useState(false);
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const creating = mode === 'create';
  return <Dialog open onOpenChange={open => { if (!open && !busy) onClose(); }}><DialogContent>
    <DialogTitle>{creating ? 'Создать аккаунты для класса' : `Сменить пароль · ${count} учеников`}</DialogTitle>
    <DialogDescription>{creating ? 'Вставьте имена учеников, каждое с новой строки. Логин сформируется автоматически. Можно указать свой: Имя;Логин.' : 'Логины останутся прежними. Старые пароли выбранных учеников перестанут работать.'}</DialogDescription>
    <form className="space-y-4" onSubmit={async event => {
      event.preventDefault(); setError('');
      const rows = creating ? parseStudentCsv(source) : [];
      if (creating && (!rows.length || rows.some(row => row.display_name.length < 2))) { setError('Введите имена учеников: не менее двух символов, каждое с новой строки.'); return; }
      if (rows.length > 200) { setError('За один раз можно добавить до 200 учеников.'); return; }
      setBusy(true);
      try { await onSubmit(rows, manual ? password : undefined, (done, total) => setProgress(`Обработано ${done} из ${total}`)); }
      catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось выполнить действие.'); }
      finally { setBusy(false); }
    }}>
      {creating && <label className="block text-sm font-semibold">Список учеников<textarea required disabled={busy} aria-label="Список учеников" rows={7} value={source} onChange={event => setSource(event.target.value)} placeholder={'Алина Осмонова\nИван Петров\nНурай Акматова;nurai.7a'} className="mt-2 w-full rounded-md border bg-background p-3 font-normal" /></label>}
      <PasswordChoice manual={manual} password={password} onManual={setManual} onPassword={setPassword} disabled={busy} />
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {busy && <p role="status" className="text-sm text-muted-foreground">{progress || 'Обрабатываем…'} Не закрывайте это окно.</p>}
      <div className="flex justify-end gap-2"><button type="button" disabled={busy} onClick={onClose} className="h-10 rounded-md border px-4">Отмена</button><button disabled={busy} className="h-10 rounded-md bg-primary px-4 font-semibold text-primary-foreground">{busy ? 'Выполняем…' : creating ? 'Создать аккаунты' : 'Сменить пароль'}</button></div>
    </form>
  </DialogContent></Dialog>;
}
