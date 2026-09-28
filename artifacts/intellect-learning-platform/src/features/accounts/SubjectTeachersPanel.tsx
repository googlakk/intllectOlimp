import { useState, type FormEvent } from 'react';
import { Ban, GraduationCap, KeyRound, Loader2, Plus, RotateCcw } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { type IssuedCredentials, type TeacherAccount, useCreateTeacher, useSetTeacherSubjects, useTeacherSubjectOptions, useTeachers } from '@/lib/api';

type Props = {
  onCredentials: (credentials: IssuedCredentials[]) => void;
  onBlock: (teacher: TeacherAccount) => void;
  onReset: (teacher: TeacherAccount) => void;
};

export function SubjectTeachersPanel({ onCredentials, onBlock, onReset }: Props) {
  const teachers = useTeachers();
  const subjects = useTeacherSubjectOptions();
  const create = useCreateTeacher();
  const update = useSetTeacherSubjects();
  const [editor, setEditor] = useState<'new' | TeacherAccount | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [success, setSuccess] = useState('');
  const [validationError, setValidationError] = useState('');
  const pending = create.isPending || update.isPending;
  const error = create.error || update.error;

  const openEditor = (value: 'new' | TeacherAccount) => {
    create.reset(); update.reset(); setSuccess(''); setValidationError('');
    setSelected(value === 'new' ? [] : value.subjects.map(subject => subject.id));
    setEditor(value);
  };
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editor || pending) return;
    const data = new FormData(event.currentTarget);
    setValidationError('');
    if (editor === 'new' && String(data.get('name')).trim().length < 2) {
      setValidationError('Введите имя учителя: не менее двух символов.'); return;
    }
    try {
      if (editor === 'new') {
        const issued = await create.mutateAsync({ login: String(data.get('login')).trim(), display_name: String(data.get('name')).trim(), subject_ids: selected });
        setEditor(null); onCredentials([issued]); setSuccess('Учитель создан. Передайте ему временные данные для входа.');
      } else {
        await update.mutateAsync({ profileId: editor.profile_id, subject_ids: selected });
        setEditor(null); setSuccess('Назначения сохранены. Учитель работает только с выбранными предметами и классами.');
      }
    } catch { /* Ошибка сохраняется в форме, выбранные назначения остаются. */ }
  };
  const groups = new Map<string, Array<{ id: number; grade: number }>>();
  for (const subject of subjects.data ?? []) groups.set(subject.name, [...(groups.get(subject.name) ?? []), subject]);

  return <section className="rounded-xl border bg-card p-5 sm:p-6" aria-labelledby="subject-teachers-heading">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><h2 id="subject-teachers-heading" className="flex items-center gap-2 text-xl font-bold"><GraduationCap className="h-6 w-6 text-primary" />Предметные учителя</h2><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Назначьте предмет и классы программы. Учитель сможет создавать и проверять уроки по уже загруженным темам.</p></div>
      <button type="button" onClick={() => openEditor('new')} className="inline-flex h-11 items-center gap-2 rounded-lg bg-primary px-4 font-semibold text-primary-foreground"><Plus className="h-4 w-4" />Создать учителя</button>
    </div>
    {subjects.error && <p role="alert" className="mt-4 rounded-lg border border-destructive/20 p-3 text-sm text-destructive">{subjects.error.message}</p>}
    {success && <p role="status" className="mt-4 rounded-lg bg-primary/10 p-3 text-sm text-primary">{success}</p>}
    {teachers.isLoading ? <p className="mt-5 flex items-center gap-2 text-sm"><Loader2 className="h-4 w-4 animate-spin" />Загружаем учителей…</p> : teachers.error ? <p role="alert" className="mt-5 text-sm text-destructive">{teachers.error.message} <button onClick={() => teachers.refetch()} className="underline">Повторить</button></p> : <div className="mt-5 divide-y">
      {teachers.data?.map(teacher => <article key={teacher.profile_id} className="flex flex-wrap items-center justify-between gap-4 py-4">
        <div className="min-w-0 flex-1"><h3 className="font-bold">{teacher.name}</h3><p className="mt-1 text-xs text-muted-foreground">{teacher.login} · {teacher.status === 'blocked' ? 'Заблокирован' : teacher.must_change_password ? 'Временный пароль' : 'Активен'}</p><div className="mt-2 flex flex-wrap gap-1.5">{teacher.subjects.map(subject => <span key={subject.id} className="rounded-md bg-muted px-2 py-1 text-xs font-medium">{subject.name} · {subject.grade} класс</span>)}{!teacher.subjects.length && <span className="text-sm text-amber-700">Предметы не назначены — темы недоступны</span>}</div></div>
        <div className="flex flex-wrap items-center gap-2"><button onClick={() => openEditor(teacher)} className="h-10 rounded-lg border px-3 text-sm font-semibold">Предметы и классы</button><button aria-label={`Сбросить пароль: ${teacher.name}`} onClick={() => onReset(teacher)} className="grid h-10 w-10 place-items-center rounded-lg border"><KeyRound className="h-4 w-4" /></button><button aria-label={`${teacher.status === 'blocked' ? 'Восстановить' : 'Заблокировать'}: ${teacher.name}`} onClick={() => onBlock(teacher)} className="grid h-10 w-10 place-items-center rounded-lg border">{teacher.status === 'blocked' ? <RotateCcw className="h-4 w-4" /> : <Ban className="h-4 w-4" />}</button></div>
      </article>)}
      {!teachers.data?.length && <p className="py-5 text-sm text-muted-foreground">Создайте первого предметного учителя. Учебный класс со списком учеников для этого не требуется.</p>}
    </div>}
    <Dialog open={editor !== null} onOpenChange={open => { if (!open && !pending) setEditor(null); }}><DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl"><DialogHeader><DialogTitle>{editor === 'new' ? 'Новый предметный учитель' : `Назначения: ${editor?.name ?? ''}`}</DialogTitle><DialogDescription>Выберите только те предметы и классы, уроками которых будет заниматься учитель. Темы и учебники берутся из загруженной программы.</DialogDescription></DialogHeader>
      <form onSubmit={submit} className="space-y-5"><fieldset disabled={pending} className="space-y-5 disabled:opacity-60">
        {editor === 'new' && <div className="grid gap-4 sm:grid-cols-2"><label className="space-y-2 text-sm font-semibold"><span>Имя и фамилия</span><input name="name" required minLength={2} maxLength={255} className="h-11 w-full rounded-lg border px-3" /></label><label className="space-y-2 text-sm font-semibold"><span>Логин латиницей</span><input name="login" required pattern="[a-zA-Z0-9._-]{3,50}" autoComplete="off" className="h-11 w-full rounded-lg border px-3" /><span className="block text-xs font-normal text-muted-foreground">От 3 до 50 символов: буквы, цифры, точка, _ и -</span></label></div>}
        <div className="space-y-3"><p className="text-sm font-semibold">Предметы и классы программы</p>{subjects.isLoading ? <p className="text-sm text-muted-foreground">Загружаем предметы…</p> : subjects.error ? <p role="alert" className="text-sm text-destructive">Не удалось загрузить предметы. <button type="button" onClick={() => subjects.refetch()} className="underline">Повторить</button></p> : !groups.size ? <p className="rounded-lg bg-muted p-3 text-sm">Сначала загрузите программу в разделе «Уроки». Затем здесь появятся предметы и классы.</p> : [...groups].sort(([a], [b]) => a.localeCompare(b, 'ru')).map(([name, variants]) => <fieldset key={name} className="rounded-lg border p-3"><legend className="px-1 text-sm font-semibold">{name}</legend><div className="flex flex-wrap gap-2">{variants.sort((a, b) => a.grade - b.grade).map(subject => <label key={subject.id} className={`inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-lg border px-3 text-sm ${selected.includes(subject.id) ? 'border-primary bg-primary/10 text-primary' : 'border-border'}`}><input type="checkbox" checked={selected.includes(subject.id)} onChange={event => setSelected(current => event.target.checked ? [...current, subject.id] : current.filter(id => id !== subject.id))} />{subject.grade} класс</label>)}</div></fieldset>)}</div>
        {editor !== 'new' && !selected.length && <p className="text-sm text-amber-700">Все назначения будут сняты. Учитель останется в системе, но не сможет открывать предметы и создавать уроки.</p>}
        {(validationError || error) && <p role="alert" className="text-sm text-destructive">{validationError || error?.message}</p>}
        <div className="flex justify-end gap-2"><button type="button" onClick={() => setEditor(null)} className="h-11 rounded-lg border px-4 font-semibold">Отмена</button><button disabled={subjects.isLoading || Boolean(subjects.error) || (editor === 'new' && !selected.length)} className="inline-flex h-11 items-center gap-2 rounded-lg bg-primary px-4 font-semibold text-primary-foreground disabled:opacity-50">{pending && <Loader2 className="h-4 w-4 animate-spin" />}{editor === 'new' ? 'Создать учителя' : 'Сохранить назначения'}</button></div>
      </fieldset></form>
    </DialogContent></Dialog>
  </section>;
}
