import { useEffect, useState } from 'react';
import { Loader2, Plus, UserMinus, Users } from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { type IssuedCredentials, type TeacherAccount, useAssignTeacher, useClassrooms, useCreateClassroom, useResetAccountPassword, useSetAccountBlocked, useTeachers, useUnassignTeacher } from '@/lib/api';
import { SubjectTeachersPanel } from './SubjectTeachersPanel';
import { StudentAccountsPanel } from './StudentAccountsPanel';
import { CredentialsDialog } from './CredentialsDialog';

export function AccountsManager() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const { data: classrooms = [], isLoading, error: classroomError } = useClassrooms();
  const [classroomId, setClassroomId] = useState<number | null>(null);
  const { data: teachers = [] } = useTeachers(isAdmin);
  const [credentials, setCredentials] = useState<IssuedCredentials[]>([]);
  const [error, setError] = useState('');
  const createClassroom = useCreateClassroom();
  const assignTeacher = useAssignTeacher();
  const unassignTeacher = useUnassignTeacher();
  const resetPassword = useResetAccountPassword();
  const setBlocked = useSetAccountBlocked();
  const classroom = classrooms.find(room => room.id === classroomId);
  useEffect(() => {
    if (!classroomId && classrooms[0]) setClassroomId(classrooms[0].id);
  }, [classroomId, classrooms]);
  const run = async (action: () => Promise<unknown>) => {
    setError('');
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось выполнить действие.'); }
  };
  return <div className="space-y-6">
    <header className="flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-3xl font-bold">{isAdmin ? 'Учителя, классы и ученики' : 'Классы и ученики'}</h1><p className="mt-1 text-muted-foreground">Управление доступом к учебной программе</p></div>{isAdmin && <ClassroomForm onSubmit={payload => void run(() => createClassroom.mutateAsync(payload))} />}</header>
    {(error || classroomError) && <p role="alert" className="whitespace-pre-line rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">{error || classroomError?.message}</p>}
    {isAdmin && <SubjectTeachersPanel onCredentials={setCredentials} onBlock={teacher => void run(() => setBlocked.mutateAsync({ profileId: teacher.profile_id, blocked: teacher.status !== 'blocked' }))} onReset={teacher => void run(async () => { const result = await resetPassword.mutateAsync(teacher.profile_id); setCredentials([{ profile_id: teacher.profile_id, display_name: teacher.name, login: teacher.login, temporary_password: result.temporary_password }]); })} />}
    {isLoading && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Загружаем учебные классы…</p>}
    <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]"><aside className="border-r pr-4"><p className="mb-3 text-xs font-bold uppercase text-muted-foreground">Учебные классы</p><div className="space-y-1">{classrooms.map(room => <button key={room.id} onClick={() => setClassroomId(room.id)} className={`w-full rounded-md px-3 py-3 text-left ${room.id === classroomId ? 'bg-primary/10 text-primary' : 'hover:bg-muted'}`}><span className="block font-semibold">{room.name}</span><span className="text-xs text-muted-foreground">{room.grade} класс · {room.student_count} учеников</span></button>)}{!classrooms.length && <p className="py-6 text-sm text-muted-foreground">Классы ещё не созданы</p>}</div></aside>
    <section className="min-w-0 space-y-5">{classroomId && classroom ? <><StudentAccountsPanel key={classroomId} classroomId={classroomId} classrooms={classrooms} onCredentials={setCredentials} onError={setError} />{isAdmin && <AdminTeacherPanel classroom={classroom} teachers={teachers} onAssign={profileId => void run(() => assignTeacher.mutateAsync({ classroom_id: classroomId, teacher_profile_id: profileId }))} onUnassign={profileId => void run(() => unassignTeacher.mutateAsync({ classroom_id: classroomId, teacher_profile_id: profileId }))} />}</> : <div className="grid min-h-64 place-items-center text-muted-foreground"><Users className="h-8 w-8" /></div>}</section></div>
    {credentials.length > 0 && <CredentialsDialog credentials={credentials} onClose={() => setCredentials([])} />}
  </div>;
}

function ClassroomForm({ onSubmit }: { onSubmit: (data: { name: string; grade: number; academic_year: string }) => void }) {
  const [open, setOpen] = useState(false);
  if (!open) return <button onClick={() => setOpen(true)} className="inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 font-semibold text-primary-foreground"><Plus className="h-4 w-4" />Создать класс</button>;
  return <form onSubmit={(e) => { e.preventDefault(); const data = new FormData(e.currentTarget); onSubmit({ name: String(data.get('name')), grade: Number(data.get('grade')), academic_year: String(data.get('year')) }); setOpen(false); }} className="flex flex-wrap gap-2"><input name="name" required placeholder="7А" className="h-10 w-24 rounded-md border px-3" /><input name="grade" required type="number" min="1" max="12" placeholder="Класс" className="h-10 w-24 rounded-md border px-3" /><input name="year" required defaultValue="2026/27" className="h-10 w-28 rounded-md border px-3" /><button className="h-10 rounded-md bg-primary px-4 font-semibold text-primary-foreground">Создать</button></form>;
}

function AdminTeacherPanel({ classroom, teachers, onAssign, onUnassign }: {
  classroom: { teachers: Array<{ profile_id: number; name: string; status: string }> };
  teachers: TeacherAccount[];
  onAssign: (id: number) => void;
  onUnassign: (id: number) => void;
}) {
  const assignedIds = new Set(classroom.teachers.map((teacher) => teacher.profile_id));
  const available = teachers.filter((teacher) => teacher.status === 'active' && !assignedIds.has(teacher.profile_id));
  return <section className="space-y-4 border-t pt-5">
    <div><h3 className="font-bold">Учителя класса</h3><div className="mt-2 flex flex-wrap gap-2">{classroom.teachers.map((teacher) => <span key={teacher.profile_id} className="inline-flex h-9 items-center gap-2 rounded-md border bg-muted/30 px-3 text-sm font-semibold">{teacher.name}{teacher.status === 'blocked' && <span className="text-destructive">заблокирован</span>}<button title="Снять назначение" onClick={() => onUnassign(teacher.profile_id)} className="text-muted-foreground hover:text-foreground"><UserMinus className="h-4 w-4" /></button></span>)}{!classroom.teachers.length && <span className="text-sm text-muted-foreground">Учитель пока не назначен</span>}</div></div>
    <p className="text-sm text-muted-foreground">Назначение в учебный класс даёт доступ к списку учеников. Предметы и классы программы назначаются отдельно, выше.</p>
    <select aria-label="Назначить учителя классу" defaultValue="" onChange={(e) => { if (e.target.value) { onAssign(Number(e.target.value)); e.target.value = ''; } }} className="h-10 rounded-md border bg-background px-3"><option value="">Назначить учителя</option>{available.map((teacher) => <option key={teacher.profile_id} value={teacher.profile_id}>{teacher.name}</option>)}</select>
  </section>;
}
