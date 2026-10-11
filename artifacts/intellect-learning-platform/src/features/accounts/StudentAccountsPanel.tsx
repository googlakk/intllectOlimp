import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Ban, KeyRound, RotateCcw, Upload, UserPlus } from 'lucide-react';
import { type Classroom, type IssuedCredentials, useClassroomStudents, useCreateStudent, useBulkCreateStudents, useResetAccountPassword, resetClassroomPasswords, useSetAccountBlocked, useTransferStudent } from '@/lib/api';
import { runCredentialBatches } from './credentialBatch';
import { StudentCredentialsDialog } from './StudentCredentialsDialog';
import type { StudentCsvRow } from './studentCsv';

type Action = { mode: 'create'; names?: string } | { mode: 'reset'; ids: number[] };

export function StudentAccountsPanel({ classroomId, classrooms, onCredentials, onError }: {
  classroomId: number; classrooms: Classroom[]; onCredentials: (items: IssuedCredentials[]) => void; onError: (message: string) => void;
}) {
  const { data: students = [], isLoading, error: loadError } = useClassroomStudents(classroomId);
  const [selected, setSelected] = useState<number[]>([]);
  const [action, setAction] = useState<Action | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const client = useQueryClient();
  const create = useCreateStudent(); const bulkCreate = useBulkCreateStudents(); const reset = useResetAccountPassword();
  const block = useSetAccountBlocked(); const transfer = useTransferStudent();
  const active = students.filter(student => student.status === 'active');
  const selectedIds = active.filter(student => selected.includes(student.profile_id)).map(student => student.profile_id);
  const run = async (fn: () => Promise<unknown>) => {
    onError(''); setBusy(true);
    try { await fn(); } catch (reason) { onError(reason instanceof Error ? reason.message : 'Не удалось выполнить действие.'); }
    finally { setBusy(false); }
  };
  const submitBatch = async (rows: StudentCsvRow[], password?: string, progress?: (done: number, total: number) => void) => {
    if (!action) return;
    const issued: IssuedCredentials[] = [];
    const failures: string[] = [];
    onError('');
    try {
      if (action.mode === 'create') {
        await runCredentialBatches(rows, batch => bulkCreate.mutateAsync({ classroom_id: classroomId, students: batch.map(row => ({ ...row, ...(password ? { temporary_password: password } : {}) })) }), (result, done, offset) => {
          issued.push(...result.created);
          failures.push(...result.errors.map(item => `Строка ${offset + item.row}: ${item.error}`));
          progress?.(done, rows.length);
        });
      } else if (action.ids.length === 1) {
        const student = students.find(item => item.profile_id === action.ids[0]);
        if (!student) throw new Error('Ученик больше не входит в этот класс.');
        const result = await reset.mutateAsync({ profileId: student.profile_id, temporary_password: password });
        issued.push({ profile_id: student.profile_id, display_name: student.name, login: student.login, temporary_password: result.temporary_password });
      } else {
        const ids = action.ids;
        await runCredentialBatches(ids, batch => resetClassroomPasswords(classroomId, batch, password), (result, done) => {
          issued.push(...result.updated);
          failures.push(...result.errors.map(item => `${item.display_name}: ${item.error}`));
          progress?.(done, ids.length);
        });
      }
    } catch (reason) {
      failures.push(reason instanceof Error ? reason.message : 'Связь прервалась.');
      failures.push('Последующие ученики не обработаны. Проверьте список перед повторным запуском.');
    } finally {
      setAction(null); setSelected([]);
      void client.invalidateQueries({ queryKey: ['accounts'] });
      onError(failures.join('\n'));
      if (issued.length) onCredentials(issued);
    }
  };
  return <div className="space-y-5">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4"><div><h2 className="text-xl font-bold">{classrooms.find(room => room.id === classroomId)?.name}</h2><p className="text-sm text-muted-foreground">{students.length} учеников</p></div><div className="flex flex-wrap gap-2">
      <input ref={fileRef} type="file" accept=".csv,.tsv,.txt" className="hidden" onChange={async event => { const file = event.target.files?.[0]; event.target.value = ''; if (file) { try { setAction({ mode: 'create', names: await file.text() }); } catch { onError('Не удалось прочитать файл.'); } } }} />
      <button disabled={busy} onClick={() => fileRef.current?.click()} className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm"><Upload className="h-4 w-4" />Импорт списка</button><button disabled={busy} onClick={() => setAction({ mode: 'create' })} className="h-10 rounded-md border px-3 text-sm font-semibold">Создать аккаунты для класса</button>
    </div></div>
    <form onSubmit={event => {
      event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
      void run(async () => {
        const login = String(data.get('login') || '').trim(); const password = String(data.get('password') || '');
        const result = await create.mutateAsync({ classroom_id: classroomId, display_name: String(data.get('name')), ...(login ? { login } : {}), ...(password ? { temporary_password: password } : {}) });
        onCredentials([result]); form.reset();
      });
    }} className="space-y-3 rounded-md border bg-muted/20 p-4"><h3 className="font-semibold">Добавить ученика</h3><div className="grid gap-3 sm:grid-cols-2"><label className="text-sm">Имя и фамилия<input name="name" required minLength={2} disabled={busy} className="mt-1 h-10 w-full rounded-md border bg-background px-3" /></label><label className="text-sm">Логин — необязательно<input name="login" disabled={busy} placeholder="Сформируется автоматически" pattern="[a-zA-Z0-9._-]{3,50}" className="mt-1 h-10 w-full rounded-md border bg-background px-3" /></label><label className="text-sm">Временный пароль — необязательно<input name="password" disabled={busy} type="text" autoComplete="off" minLength={6} maxLength={128} pattern="\S{6,128}" placeholder="Сформируется простой пароль" className="mt-1 h-10 w-full rounded-md border bg-background px-3" /></label><button disabled={busy} className="mt-auto inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 font-semibold text-primary-foreground"><UserPlus className="h-4 w-4" />{create.isPending ? 'Создаём…' : 'Добавить ученика'}</button></div></form>
    <div className="flex flex-wrap items-center gap-2"><button disabled={busy || !active.length} onClick={() => setAction({ mode: 'reset', ids: active.map(student => student.profile_id) })} className="h-10 rounded-md border px-3 text-sm font-semibold">Сменить пароли всего класса</button><button disabled={busy || !selectedIds.length} onClick={() => setAction({ mode: 'reset', ids: selectedIds })} className="h-10 rounded-md border px-3 text-sm">Сменить выбранным ({selectedIds.length})</button><p className="text-xs text-muted-foreground">Массовая смена доступна для активных учеников.</p></div>
    {isLoading && <p role="status">Загружаем учеников…</p>}{loadError && <p role="alert" className="text-sm text-destructive">{loadError.message}</p>}
    <div className="overflow-x-auto rounded-md border"><table className="w-full text-sm"><thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground"><tr><th className="p-3"><input type="checkbox" aria-label="Выбрать всех активных учеников" checked={active.length > 0 && selectedIds.length === active.length} disabled={busy || !active.length} onChange={event => setSelected(event.target.checked ? active.map(student => student.profile_id) : [])} /></th><th className="p-3">Ученик</th><th className="p-3">Логин</th><th className="p-3">Статус</th><th className="p-3 text-right">Действия</th></tr></thead><tbody>{students.map(student => <tr key={student.profile_id} className="border-t"><td className="p-3"><input type="checkbox" aria-label={`Выбрать: ${student.name}`} checked={selectedIds.includes(student.profile_id)} disabled={busy || student.status !== 'active'} onChange={event => setSelected(ids => event.target.checked ? [...ids, student.profile_id] : ids.filter(id => id !== student.profile_id))} /></td><td className="p-3 font-semibold">{student.name}</td><td className="p-3 font-mono text-xs">{student.login}</td><td className="p-3">{student.status === 'blocked' ? 'Заблокирован' : student.must_change_password ? 'Временный пароль' : 'Активен'}</td><td className="p-3"><div className="flex justify-end gap-1"><button disabled={busy} aria-label={`Сменить пароль: ${student.name}`} title="Сменить пароль" onClick={() => setAction({ mode: 'reset', ids: [student.profile_id] })} className="grid h-9 w-9 place-items-center rounded-md hover:bg-muted"><KeyRound className="h-4 w-4" /></button><button disabled={busy} title={student.status === 'blocked' ? 'Восстановить' : 'Заблокировать'} onClick={() => void run(() => block.mutateAsync({ profileId: student.profile_id, blocked: student.status !== 'blocked' }))} className="grid h-9 w-9 place-items-center rounded-md hover:bg-muted">{student.status === 'blocked' ? <RotateCcw className="h-4 w-4" /> : <Ban className="h-4 w-4" />}</button>{classrooms.length > 1 && <select disabled={busy} aria-label={`Перевести: ${student.name}`} defaultValue="" onChange={event => { const value = event.target.value; event.target.value = ''; if (value) void run(() => transfer.mutateAsync({ profileId: student.profile_id, target_classroom_id: Number(value) })); }} className="h-9 rounded-md border bg-background px-2"><option value="">Перевести</option>{classrooms.filter(room => room.id !== classroomId).map(room => <option key={room.id} value={room.id}>{room.name}</option>)}</select>}</div></td></tr>)}{!isLoading && !loadError && !students.length && <tr><td colSpan={5} className="p-5 text-muted-foreground">Добавьте ученика или создайте аккаунты по списку класса.</td></tr>}</tbody></table></div>
    {action && <StudentCredentialsDialog mode={action.mode} count={action.mode === 'reset' ? action.ids.length : undefined} names={action.mode === 'create' ? action.names : undefined} onClose={() => setAction(null)} onSubmit={submitBatch} />}
  </div>;
}
