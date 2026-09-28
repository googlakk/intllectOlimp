import { useId, useState } from 'react';
import { Link } from 'wouter';
import { useSubjects, useTeacherOutline } from '@/lib/api';
import { catalogLessonChoices, componentLessonPath } from './lessonPicker';

export function CatalogLessonPicker({ componentId }: { componentId: string }) {
  const [open, setOpen] = useState(false);
  return <section className="rounded-xl border border-primary/20 bg-primary/5 p-4">
    <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open} className="rounded-lg bg-primary px-4 py-3 text-sm font-bold text-primary-foreground">{open ? 'Скрыть выбор урока' : 'Подготовить для моего урока'}</button>
    {open && <LessonChoices componentId={componentId} />}
  </section>;
}

function LessonChoices({ componentId }: { componentId: string }) {
  const { data: subjects, isLoading, isError, refetch } = useSubjects();
  const [subjectId, setSubjectId] = useState(0);
  const [query, setQuery] = useState('');
  const subjectSelectId = useId();
  const outline = useTeacherOutline(subjectId);
  const choices = catalogLessonChoices(outline.data, query);
  return <div className="mt-4 space-y-3">
    <p className="text-sm text-muted-foreground">Выберите существующий урок. В редакторе сможете подготовить блок по его теме и целям.</p>
    {isLoading && <p role="status" className="text-sm">Загружаем предметы…</p>}
    {isError && <p role="alert" className="text-sm text-destructive">Не удалось загрузить предметы. <button onClick={() => void refetch()} className="underline">Повторить</button></p>}
    {!isLoading && !isError && subjects?.length === 0 && <p className="text-sm">Пока нет предметов. <Link href="/dashboard/lessons" className="text-primary underline">Перейти к урокам</Link></p>}
    {subjects && subjects.length > 0 && <><label htmlFor={subjectSelectId} className="block text-sm font-semibold">Предмет и класс</label><select id={subjectSelectId} value={subjectId} onChange={(event) => { setSubjectId(Number(event.target.value)); setQuery(''); }} className="w-full rounded-lg border bg-background p-3 text-base"><option value={0}>Выберите предмет</option>{subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.name} · {subject.grade} класс</option>)}</select></>}
    {subjectId > 0 && <>
      <input aria-label="Поиск урока по теме КТП" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Название темы или номер КТП" className="w-full rounded-lg border bg-background p-3 text-base" />
      {outline.isLoading && <p role="status" className="text-sm">Загружаем уроки…</p>}
      {outline.isError && <p role="alert" className="text-sm text-destructive">Не удалось загрузить уроки. <button onClick={() => void outline.refetch()} className="underline">Повторить</button></p>}
      {!outline.isLoading && !outline.isError && choices.length === 0 && <p className="text-sm text-muted-foreground">{query ? 'По этому запросу уроков нет.' : 'В этом предмете пока нет созданных уроков.'}</p>}
      {!outline.isError && <ul className="max-h-64 space-y-2 overflow-y-auto">{choices.map(({ topic, sectionName }) => <li key={topic.id}><Link href={componentLessonPath(topic.id, componentId)} className="block rounded-lg border bg-background p-3 hover:border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"><span className="block text-sm font-semibold">{topic.ktp_number ? `${topic.ktp_number}. ` : ''}{topic.name}</span><span className="mt-1 block text-xs text-muted-foreground">{sectionName} · {topic.lesson_status === 'published' ? 'Опубликован' : 'Черновик'}</span></Link></li>)}</ul>}
    </>}
  </div>;
}
