import { useState } from 'react';
import { useCreateCourse, useCreateSection } from '@/lib/api';

export function CreateCourse({ onCreated }: { onCreated: (id: number, grade: number) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [grade, setGrade] = useState(7);
  const create = useCreateCourse();
  if (!open) return <button onClick={() => setOpen(true)} className="rounded-lg border px-4 py-2 font-semibold">Создать программу</button>;
  return <form className="space-y-3 rounded-lg border bg-card p-4" onSubmit={async event => {
    event.preventDefault();
    try { const subject = await create.mutateAsync({ name: name.trim(), grade }); onCreated(subject.id, grade); setOpen(false); } catch { /* retain values */ }
  }}><h2 className="font-bold">Новая программа без КТП</h2><label className="block text-sm">Предмет<input required maxLength={255} autoFocus value={name} onChange={event => setName(event.target.value)} className="mt-1 w-full rounded border bg-background p-2" /></label><label className="block text-sm">Класс<input type="number" min={1} max={12} required value={grade} onChange={event => setGrade(Number(event.target.value))} className="ml-3 w-20 rounded border bg-background p-2" /></label>{create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}<div className="flex gap-3"><button disabled={create.isPending || !name.trim()} className="rounded bg-primary px-3 py-2 text-primary-foreground">{create.isPending ? 'Создаём…' : 'Создать'}</button><button type="button" onClick={() => setOpen(false)}>Отмена</button></div></form>;
}

export function CreateSection({ subjectId }: { subjectId: number }) {
  const [name, setName] = useState('');
  const [open, setOpen] = useState(false);
  const create = useCreateSection();
  if (!open) return <button onClick={() => setOpen(true)} className="rounded-lg border px-4 py-2 font-semibold">Добавить раздел</button>;
  return <form onSubmit={async event => { event.preventDefault(); try { await create.mutateAsync({ subjectId, name: name.trim() }); setOpen(false); setName(''); } catch { /* retain values */ } }} className="space-y-3 rounded-lg border p-4"><label className="block text-sm font-semibold">Название раздела<input required maxLength={255} value={name} onChange={event => setName(event.target.value)} className="ml-2 rounded border bg-background p-2" autoFocus /></label>{create.error && <p role="alert" className="text-sm text-destructive">{create.error.message}</p>}<div className="flex gap-3"><button disabled={create.isPending || !name.trim()} className="rounded bg-primary px-3 py-2 text-primary-foreground">{create.isPending ? 'Сохраняется…' : 'Добавить'}</button><button type="button" onClick={() => setOpen(false)}>Отмена</button></div></form>;
}
