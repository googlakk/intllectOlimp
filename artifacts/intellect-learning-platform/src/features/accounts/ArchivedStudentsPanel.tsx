import { useState } from 'react';
import { type ArchivedStudent, type Classroom, useArchivedStudents, useRestoreStudentAccount } from '@/lib/api';

export function ArchivedStudentsPanel({ classrooms }: { classrooms: Classroom[] }) {
  const [open, setOpen] = useState(false);
  const { data: students = [], isLoading, error } = useArchivedStudents(open);
  return <section className="space-y-3 border-t pt-5">
    <button type="button" aria-expanded={open} onClick={() => setOpen(value => !value)} className="h-11 rounded-md border px-4 text-sm font-semibold">Удалённые ученики</button>
    {open && <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Выберите класс, чтобы вернуть ученика. Логин, пароль и история обучения сохраняются.</p>
      {isLoading && <p role="status">Загружаем удалённых учеников…</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
      {!isLoading && !error && !students.length && <p className="text-sm text-muted-foreground">Удалённых учеников нет.</p>}
      {students.map(student => <ArchivedStudentRow key={student.profile_id} student={student} classrooms={classrooms} />)}
    </div>}
  </section>;
}

function ArchivedStudentRow({ student, classrooms }: { student: ArchivedStudent; classrooms: Classroom[] }) {
  const [classroomId, setClassroomId] = useState<number | null>(classrooms.find(room => room.grade === student.grade)?.id ?? null);
  const [error, setError] = useState('');
  const restore = useRestoreStudentAccount();
  return <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3">
    <div className="min-w-0"><p className="font-semibold">{student.name}</p><p className="break-all font-mono text-xs text-muted-foreground">{student.login}</p></div>
    <div className="flex flex-wrap gap-2">
      <select disabled={restore.isPending} aria-label={`Класс для восстановления: ${student.name}`} value={classroomId ?? ''} onChange={event => setClassroomId(event.target.value ? Number(event.target.value) : null)} className="h-11 rounded-md border bg-background px-3">
        <option value="">Выберите класс</option>{classrooms.map(room => <option key={room.id} value={room.id}>{room.name}</option>)}
      </select>
      <button disabled={!classroomId || restore.isPending} onClick={async () => {
        if (!classroomId) return;
        setError('');
        try { await restore.mutateAsync({ profileId: student.profile_id, targetClassroomId: classroomId }); }
        catch (reason) { setError(reason instanceof Error ? reason.message : 'Не удалось восстановить ученика.'); }
      }} className="h-11 rounded-md border px-3 text-sm font-semibold">{restore.isPending ? 'Восстанавливаем…' : 'Восстановить ученика'}</button>
    </div>
    {error && <p role="alert" className="w-full text-sm text-destructive">{error}</p>}
  </div>;
}
