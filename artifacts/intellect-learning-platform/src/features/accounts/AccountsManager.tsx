import { useEffect, useRef, useState } from 'react';
import { Ban, Copy, KeyRound, Loader2, Plus, RotateCcw, Upload, UserMinus, UserPlus, Users } from 'lucide-react';

import { useAuth } from '@/components/auth/AuthContext';
import {
  type IssuedCredentials,
  type TeacherAccount,
  useAssignTeacher,
  useBulkCreateStudents,
  useClassrooms,
  useClassroomStudents,
  useCreateClassroom,
  useCreateStudent,
  useCreateTeacher,
  useResetAccountPassword,
  useSetAccountBlocked,
  useTeachers,
  useTransferStudent,
  useUnassignTeacher,
} from '@/lib/api';
import { parseStudentCsv } from './studentCsv';

export function AccountsManager() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const { data: classrooms = [], isLoading } = useClassrooms();
  const [classroomId, setClassroomId] = useState<number | null>(null);
  const { data: students = [] } = useClassroomStudents(classroomId);
  const { data: teachers = [] } = useTeachers(isAdmin);
  const [credentials, setCredentials] = useState<IssuedCredentials[]>([]);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const createClassroom = useCreateClassroom();
  const createStudent = useCreateStudent();
  const createTeacher = useCreateTeacher();
  const assignTeacher = useAssignTeacher();
  const unassignTeacher = useUnassignTeacher();
  const bulkCreate = useBulkCreateStudents();
  const resetPassword = useResetAccountPassword();
  const setBlocked = useSetAccountBlocked();
  const transferStudent = useTransferStudent();

  useEffect(() => {
    if (!classroomId && classrooms[0]) setClassroomId(classrooms[0].id);
  }, [classroomId, classrooms]);

  const run = async (action: () => Promise<unknown>) => {
    setError('');
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось выполнить действие.'); }
  };

  const submitStudent = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!classroomId) return;
    const data = new FormData(event.currentTarget);
    run(async () => {
      const issued = await createStudent.mutateAsync({
        classroom_id: classroomId,
        display_name: String(data.get('name')),
        login: String(data.get('login')),
      });
      setCredentials([issued]);
      event.currentTarget.reset();
    });
  };

  const importCsv = async (file?: File) => {
    if (!file || !classroomId) return;
    const rows = parseStudentCsv(await file.text());
    if (!rows.length) {
      setError('В файле не найдено строк вида «Имя;Логин».');
      return;
    }
    await run(async () => {
      const result = await bulkCreate.mutateAsync({ classroom_id: classroomId, students: rows });
      setCredentials(result.created);
      if (result.errors.length) setError(`Не созданы строки: ${result.errors.map((item) => item.row).join(', ')}`);
    });
  };

  if (isLoading) return <div className="grid min-h-64 place-items-center"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="text-3xl font-bold">Классы и ученики</h1><p className="mt-1 text-muted-foreground">Управление доступом к учебной программе</p></div>
        {isAdmin && <ClassroomForm onSubmit={(payload) => run(() => createClassroom.mutateAsync(payload))} />}
      </header>
      {error && <p role="alert" className="rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="border-r pr-4">
          <p className="mb-3 text-xs font-bold uppercase text-muted-foreground">Учебные классы</p>
          <div className="space-y-1">
            {classrooms.map((room) => <button key={room.id} onClick={() => setClassroomId(room.id)} className={`w-full rounded-md px-3 py-3 text-left ${room.id === classroomId ? 'bg-primary/10 text-primary' : 'hover:bg-muted'}`}>
              <span className="block font-semibold">{room.name}</span><span className="text-xs text-muted-foreground">{room.grade} класс · {room.student_count} учеников</span>
            </button>)}
            {!classrooms.length && <p className="py-6 text-sm text-muted-foreground">Классы ещё не созданы</p>}
          </div>
        </aside>
        <section className="min-w-0 space-y-5">
          {classroomId ? <>
            <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
              <div><h2 className="text-xl font-bold">{classrooms.find((room) => room.id === classroomId)?.name}</h2><p className="text-sm text-muted-foreground">{students.length} учеников</p></div>
              <div className="flex gap-2">
                <input ref={fileRef} type="file" accept=".csv,.tsv,.txt" className="hidden" onChange={(e) => importCsv(e.target.files?.[0])} />
                <button onClick={() => fileRef.current?.click()} className="inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm font-semibold"><Upload className="h-4 w-4" />Импорт CSV</button>
              </div>
            </div>
            <form onSubmit={submitStudent} className="grid gap-3 rounded-md border bg-muted/20 p-4 sm:grid-cols-[1fr_1fr_auto]">
              <input name="name" required placeholder="Имя и фамилия" className="h-10 rounded-md border bg-background px-3" />
              <input name="login" required placeholder="Логин латиницей" pattern="[a-zA-Z0-9._-]{3,50}" className="h-10 rounded-md border bg-background px-3" />
              <button className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-4 font-semibold text-primary-foreground"><UserPlus className="h-4 w-4" />Добавить</button>
            </form>
            <div className="overflow-x-auto rounded-md border">
              <table className="w-full text-sm"><thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground"><tr><th className="p-3">Ученик</th><th className="p-3">Логин</th><th className="p-3">Статус</th><th className="p-3 text-right">Действия</th></tr></thead>
                <tbody>{students.map((student) => <tr key={student.profile_id} className="border-t"><td className="p-3 font-semibold">{student.name}</td><td className="p-3 font-mono text-xs">{student.login}</td><td className="p-3">{student.status === 'blocked' ? 'Заблокирован' : student.must_change_password ? 'Временный пароль' : 'Активен'}</td><td className="p-3"><div className="flex justify-end gap-1">
                  <button title="Сбросить пароль" onClick={() => run(async () => { const result = await resetPassword.mutateAsync(student.profile_id); setCredentials([{ profile_id: student.profile_id, login: student.login, temporary_password: result.temporary_password }]); })} className="grid h-8 w-8 place-items-center rounded-md hover:bg-muted"><KeyRound className="h-4 w-4" /></button>
                  <button title={student.status === 'blocked' ? 'Восстановить' : 'Заблокировать'} onClick={() => run(() => setBlocked.mutateAsync({ profileId: student.profile_id, blocked: student.status !== 'blocked' }))} className="grid h-8 w-8 place-items-center rounded-md hover:bg-muted">{student.status === 'blocked' ? <RotateCcw className="h-4 w-4" /> : <Ban className="h-4 w-4" />}</button>
                  {classrooms.length > 1 && <select title="Перевести в другой класс" defaultValue="" onChange={(e) => { if (e.target.value) run(() => transferStudent.mutateAsync({ profileId: student.profile_id, target_classroom_id: Number(e.target.value) })); }} className="h-8 rounded-md border bg-background px-2"><option value="">Перевести</option>{classrooms.filter((room) => room.id !== classroomId).map((room) => <option key={room.id} value={room.id}>{room.name}</option>)}</select>}
                </div></td></tr>)}</tbody>
              </table>
            </div>
            {isAdmin && <AdminTeacherPanel
              classroom={classrooms.find((room) => room.id === classroomId)!}
              teachers={teachers}
              onCreate={(payload) => run(async () => setCredentials([await createTeacher.mutateAsync(payload)]))}
              onAssign={(profileId) => run(() => assignTeacher.mutateAsync({ classroom_id: classroomId, teacher_profile_id: profileId }))}
              onUnassign={(profileId) => run(() => unassignTeacher.mutateAsync({ classroom_id: classroomId, teacher_profile_id: profileId }))}
              onBlock={(teacher) => run(() => setBlocked.mutateAsync({ profileId: teacher.profile_id, blocked: teacher.status !== 'blocked' }))}
              onReset={(teacher) => run(async () => { const result = await resetPassword.mutateAsync(teacher.profile_id); setCredentials([{ profile_id: teacher.profile_id, login: teacher.login, temporary_password: result.temporary_password }]); })}
            />}
          </> : <div className="grid min-h-64 place-items-center text-muted-foreground"><Users className="h-8 w-8" /></div>}
        </section>
      </div>
      {credentials.length > 0 && <CredentialsDialog credentials={credentials} onClose={() => setCredentials([])} />}
    </div>
  );
}

function ClassroomForm({ onSubmit }: { onSubmit: (data: { name: string; grade: number; academic_year: string }) => void }) {
  const [open, setOpen] = useState(false);
  if (!open) return <button onClick={() => setOpen(true)} className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 font-semibold text-primary-foreground"><Plus className="h-4 w-4" />Создать класс</button>;
  return <form onSubmit={(e) => { e.preventDefault(); const data = new FormData(e.currentTarget); onSubmit({ name: String(data.get('name')), grade: Number(data.get('grade')), academic_year: String(data.get('year')) }); setOpen(false); }} className="flex flex-wrap gap-2"><input name="name" required placeholder="7А" className="h-10 w-24 rounded-md border px-3" /><input name="grade" required type="number" min="1" max="12" placeholder="Класс" className="h-10 w-24 rounded-md border px-3" /><input name="year" required defaultValue="2026/27" className="h-10 w-28 rounded-md border px-3" /><button className="h-10 rounded-md bg-primary px-4 font-semibold text-primary-foreground">Создать</button></form>;
}

function AdminTeacherPanel({ classroom, teachers, onCreate, onAssign, onUnassign, onBlock, onReset }: {
  classroom: { teachers: Array<{ profile_id: number; name: string; status: string }> };
  teachers: TeacherAccount[];
  onCreate: (data: { login: string; display_name: string }) => void;
  onAssign: (id: number) => void;
  onUnassign: (id: number) => void;
  onBlock: (teacher: TeacherAccount) => void;
  onReset: (teacher: TeacherAccount) => void;
}) {
  const assignedIds = new Set(classroom.teachers.map((teacher) => teacher.profile_id));
  const available = teachers.filter((teacher) => teacher.status === 'active' && !assignedIds.has(teacher.profile_id));
  return <section className="space-y-4 border-t pt-5">
    <div><h3 className="font-bold">Учителя класса</h3><div className="mt-2 flex flex-wrap gap-2">{classroom.teachers.map((teacher) => <span key={teacher.profile_id} className="inline-flex h-9 items-center gap-2 rounded-md border bg-muted/30 px-3 text-sm font-semibold">{teacher.name}{teacher.status === 'blocked' && <span className="text-destructive">заблокирован</span>}<button title="Снять назначение" onClick={() => onUnassign(teacher.profile_id)} className="text-muted-foreground hover:text-foreground"><UserMinus className="h-4 w-4" /></button></span>)}{!classroom.teachers.length && <span className="text-sm text-muted-foreground">Учитель пока не назначен</span>}</div></div>
    <div className="flex flex-wrap gap-2"><select defaultValue="" onChange={(e) => { if (e.target.value) { onAssign(Number(e.target.value)); e.target.value = ''; } }} className="h-10 rounded-md border bg-background px-3"><option value="">Назначить учителя</option>{available.map((teacher) => <option key={teacher.profile_id} value={teacher.profile_id}>{teacher.name}</option>)}</select><form onSubmit={(e) => { e.preventDefault(); const data = new FormData(e.currentTarget); onCreate({ display_name: String(data.get('name')), login: String(data.get('login')) }); e.currentTarget.reset(); }} className="flex flex-wrap gap-2"><input name="name" required placeholder="Имя учителя" className="h-10 rounded-md border px-3" /><input name="login" required placeholder="Логин" pattern="[a-zA-Z0-9._-]{3,50}" className="h-10 rounded-md border px-3" /><button className="h-10 rounded-md border px-3 font-semibold">Создать учителя</button></form></div>
    <div className="overflow-x-auto rounded-md border"><table className="w-full text-sm"><thead className="bg-muted/50 text-left text-xs uppercase text-muted-foreground"><tr><th className="p-3">Учитель</th><th className="p-3">Логин</th><th className="p-3">Статус</th><th className="p-3 text-right">Действия</th></tr></thead><tbody>{teachers.map((teacher) => <tr key={teacher.profile_id} className="border-t"><td className="p-3 font-semibold">{teacher.name}</td><td className="p-3 font-mono text-xs">{teacher.login}</td><td className="p-3">{teacher.status === 'blocked' ? 'Заблокирован' : teacher.must_change_password ? 'Временный пароль' : 'Активен'}</td><td className="p-3"><div className="flex justify-end gap-1"><button title="Сбросить пароль" onClick={() => onReset(teacher)} className="grid h-8 w-8 place-items-center rounded-md hover:bg-muted"><KeyRound className="h-4 w-4" /></button><button title={teacher.status === 'blocked' ? 'Восстановить' : 'Заблокировать'} onClick={() => onBlock(teacher)} className="grid h-8 w-8 place-items-center rounded-md hover:bg-muted">{teacher.status === 'blocked' ? <RotateCcw className="h-4 w-4" /> : <Ban className="h-4 w-4" />}</button></div></td></tr>)}</tbody></table></div>
  </section>;
}

function CredentialsDialog({ credentials, onClose }: { credentials: IssuedCredentials[]; onClose: () => void }) {
  const text = credentials.map((item) => `${item.login};${item.temporary_password}`).join('\n');
  return <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"><section role="dialog" aria-modal="true" aria-label="Временные данные для входа" className="w-full max-w-lg rounded-lg bg-card p-6 shadow-xl"><h2 className="text-xl font-bold">Временные данные для входа</h2><p className="mt-2 text-sm text-muted-foreground">Они показываются один раз. Передайте каждую строку соответствующему пользователю.</p><pre className="mt-4 max-h-64 overflow-auto rounded-md bg-muted p-4 text-sm">{text}</pre><div className="mt-5 flex justify-end gap-2"><button onClick={() => navigator.clipboard.writeText(text)} className="inline-flex h-10 items-center gap-2 rounded-md border px-4 font-semibold"><Copy className="h-4 w-4" />Копировать</button><button onClick={onClose} className="h-10 rounded-md bg-primary px-4 font-semibold text-primary-foreground">Готово</button></div></section></div>;
}
