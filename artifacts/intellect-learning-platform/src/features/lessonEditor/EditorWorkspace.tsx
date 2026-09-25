import { useEffect, useState } from 'react';
import { Link } from 'wouter';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/components/auth/AuthContext';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import { useAiModels, useCreateLessonDraft, useGetLesson, useTopic, useTeacherOutline } from '@/lib/api';
import { getLessonQualityState } from '@/features/lessons/quality';
import { useLessonEditorWorkflow, lessonEditorInvalidationKeys } from './workflow';
import TopicForm from '@/features/teacherLessons/TopicForm';
import LessonPlanningSummary from './LessonPlanningSummary';
import AvatarConfigurationPanel from './AvatarConfigurationPanel';
import LessonBlockBuilder from './LessonBlockBuilder';
import { primarySectionLabel, readLessonTextbook } from '@/features/textbooks/lessonSource';
import ModelPicker, { useModelChoice } from './ModelPicker';
import { LessonIllustrationsPanel, useLessonIllustrations } from './IllustrationsPanel';

export default function EditorWorkspace({ topicId }: { topicId: number }) {
  const { user } = useAuth();
  const client = useQueryClient();
  const topicQuery = useTopic(topicId);
  const lessonQuery = useGetLesson(topicId, 'teacher');
  const topic = topicQuery.data;
  const lesson = lessonQuery.data;
  const subjectId = topic?.subject_id || Number(sessionStorage.getItem('teacher-subject')) || 0;
  const outline = useTeacherOutline(subjectId);
  const section = outline.data?.find(item => item.id === topic?.section_id);
  const workflow = useLessonEditorWorkflow(topicId, lesson);
  const createDraft = useCreateLessonDraft();
  const aiModels = useAiModels();
  const lessonModel = useModelChoice(aiModels.data?.lesson, 'intellect:lesson-model');
  const imageModel = useModelChoice(aiModels.data?.image, 'intellect:image-model');
  const illustrations = useLessonIllustrations(topicId, imageModel.requestModel);
  const usedModel = generationModelLabel(lesson?.lesson_metadata?.generation_model, aiModels.data?.lesson.options);
  const [unsaved, setUnsaved] = useState(false);
  const [step, setStep] = useState(() => new URLSearchParams(window.location.search).has('preview') ? 3 : 2);
  const [acknowledged, setAcknowledged] = useState(false);
  useEffect(() => setAcknowledged(false), [lesson?.active_version_id]);
  const quality = getLessonQualityState(lesson, acknowledged);
  const blocks = lesson?.blocks ?? [];
  const published = lesson?.status === 'published';
  const canUpdate = published && lesson?.has_unpublished_changes;
  const busy = workflow.publishLessonMutation.isPending || workflow.unpublishLessonMutation.isPending || workflow.generateLessonMutation.isPending || illustrations.running;
  const error = workflow.publishLessonMutation.error || workflow.unpublishLessonMutation.error || workflow.generateLessonMutation.error || createDraft.error;
  return <div className="mx-auto max-w-6xl space-y-6 pb-12">
    <Link href="/dashboard/lessons" className="text-sm font-semibold text-muted-foreground">← Назад к программе</Link>
    <header><h1 className="text-2xl font-bold">{topic?.name || lesson?.lesson_document?.title || 'Подготовка урока'}</h1><p className="mt-2 text-sm text-muted-foreground">{published ? canUpdate ? 'Опубликован · есть изменения в черновике' : 'Опубликован' : 'Черновик'}{published && ' — ученики видят опубликованную версию.'}</p></header>
    <nav aria-label="Шаги создания урока" className="grid grid-cols-3 gap-2">{['Тема', 'Материалы', 'Проверка и публикация'].map((label, index) => <button key={label} type="button" disabled={unsaved} onClick={() => setStep(index + 1)} aria-current={step === index + 1 ? 'step' : undefined} className={`rounded-lg border p-3 text-sm font-bold ${step === index + 1 ? 'border-primary bg-primary/10 text-primary' : 'border-border'}`}>{index + 1}. {label}</button>)}</nav>
    {error && <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">{error.message}</p>}
    {(topicQuery.error || lessonQuery.error) && <div role="alert" className="rounded-lg border p-4">Не удалось загрузить урок. <button onClick={() => { void topicQuery.refetch(); void lessonQuery.refetch(); }} className="underline">Повторить</button></div>}
    {lessonQuery.isLoading || topicQuery.isLoading ? <p role="status">Загрузка урока…</p> : topic?.archived_at ? <p>Этот урок в архиве. Восстановите его в программе, чтобы продолжить редактирование.</p> : <>
      {step === 1 && <>{section && topic ? <TopicForm key={topic.id} section={section} topic={topic} onClose={() => setStep(2)} /> : <div className="rounded-lg border p-5"><h2 className="font-bold">{topic?.name}</h2><p className="mt-2">{topic?.learning_objectives}</p><Link href="/dashboard/lessons" className="underline">Открыть предмет в программе для изменения темы</Link></div>}</>}
      {step === 2 && <section className="rounded-xl border bg-card p-4 md:p-6">
        <h2 className="text-xl font-bold">Подготовьте материалы</h2><p className="mt-2 text-sm text-muted-foreground">ИИ подготовит черновик. Проверьте объяснение, примеры и задания или добавьте их вручную.</p>
        <div className="mt-5 max-w-md"><ModelPicker label="Модель для плана урока" group={aiModels.data?.lesson} choice={lessonModel} disabled={busy} loadError={aiModels.isError} /></div>
        {usedModel && <p className="mt-2 text-xs text-muted-foreground">Текущий черновик подготовлен моделью: {usedModel}</p>}
        <LessonIllustrationsPanel lesson={lesson} state={illustrations} imageGroup={aiModels.data?.image} imageChoice={imageModel} disabled={busy && !illustrations.running} />
        <div className="my-5 flex flex-wrap gap-3"><button type="button" onClick={() => workflow.generateLesson(lessonModel.requestModel, (generated) => { if (illustrations.enabled) void illustrations.start(generated); })} disabled={busy || unsaved} className="rounded-lg bg-primary px-5 py-3 font-bold text-primary-foreground disabled:opacity-50">{workflow.generateLessonMutation.isPending ? 'Готовим черновик…' : blocks.length ? 'Заменить черновик с помощью ИИ' : 'Подготовить черновик'}</button>
        {!lesson && <button type="button" disabled={createDraft.isPending || busy} onClick={async () => {
          if (!user) return;
          try { await createDraft.mutateAsync({ topic_id: topicId, teacher_id: user.id }); await Promise.all(lessonEditorInvalidationKeys(topicId).map(queryKey => client.invalidateQueries({ queryKey }))); } catch { /* Error is displayed above. */ }
        }} className="rounded-lg border px-5 py-3 font-bold">{createDraft.isPending ? 'Создаём…' : 'Добавить материалы вручную'}</button>}</div>
        {lesson && blocks.length > 0 && <LessonTextbookNote metadata={lesson.lesson_metadata} />}
        {lesson && <LessonBlockBuilder lesson={lesson} topicId={topicId} onUnsavedChange={setUnsaved} />}
        {lesson && <details className="mt-6 rounded-lg border p-4"><summary className="cursor-pointer text-sm font-semibold">Дополнительные настройки: медиа, аватар и структура</summary><LessonPlanningSummary lesson={lesson} /><AvatarConfigurationPanel lesson={lesson} /></details>}
        {blocks.length > 0 && <button type="button" disabled={unsaved} onClick={() => setStep(3)} className="mt-6 rounded-lg bg-primary px-5 py-3 font-bold text-primary-foreground">Проверить и опубликовать →</button>}
      </section>}
      {step === 3 && <section className="space-y-5">
        <div className="rounded-xl border bg-card p-5"><h2 className="text-xl font-bold">Готовность к публикации</h2>
          {!blocks.length && <p className="mt-2">Сначала добавьте материалы урока.</p>}
          {quality.blockingIssues.length > 0 && <div data-testid="status-quality-blocked" role="alert" className="mt-3 text-sm text-destructive"><p className="font-bold">Исправьте перед публикацией:</p><ul className="ml-5 list-disc">{quality.blockingIssues.map((item, index) => <li key={index}>{item}</li>)}</ul><button onClick={() => setStep(2)} className="mt-2 underline font-semibold">Перейти к материалам</button></div>}
          {quality.warningMessages.length > 0 && <div className="mt-3 text-sm"><p className="font-bold">Рекомендации для проверки</p><ul className="ml-5 list-disc">{quality.warningMessages.map((item, index) => <li key={index}>{item}</li>)}</ul><label className="mt-3 flex items-center gap-2"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />Я проверил рекомендации</label></div>}
          <div className="mt-5 flex flex-wrap gap-3"><button type="button" disabled={busy || !blocks.length || ((!published || canUpdate) && !quality.canPublish)} onClick={() => workflow.togglePublication(acknowledged)} className="rounded-lg bg-primary px-5 py-3 font-bold text-primary-foreground disabled:opacity-50">{busy ? 'Сохраняется…' : canUpdate ? 'Обновить публикацию' : published ? 'Снять с публикации' : 'Опубликовать'}</button><button onClick={() => setStep(2)} className="rounded-lg border px-5 py-3 font-semibold">Продолжить редактирование</button></div>
          {quality.coverage.length > 0 && <details className="mt-4"><summary className="cursor-pointer text-sm font-semibold">Проверка целей обучения</summary><ul className="mt-3 space-y-2">{quality.coverage.map(item => <li key={item.objective.id} className="text-sm">{item.objective.text}: {item.explanation ? '✓' : '—'} объяснение · {item.practice ? '✓' : '—'} практика · {item.assessment ? '✓' : '—'} проверка</li>)}</ul></details>}
        </div>
        <div className="rounded-xl border bg-card p-4 md:p-6"><h2 className="mb-5 text-xl font-bold">Урок глазами ученика</h2><p className="mb-4 text-sm text-muted-foreground">Предпросмотр черновика. Ваши ответы здесь не сохраняются в результатах учеников.</p><BlockRenderer key={lesson?.active_version_id ?? 'preview'} blocks={blocks} /></div>
      </section>}
    </>}
  </div>;
}

/** По какому учебнику построен черновик — или предупреждение, что без учебника. */
function LessonTextbookNote({ metadata }: { metadata: Record<string, unknown> | null | undefined }) {
  const textbook = readLessonTextbook(metadata);
  const section = primarySectionLabel(textbook);
  if (textbook && section) {
    return <p className="mb-4 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
      Черновик построен по учебнику «{textbook.title}»: {section}. У блоков указано, на какую страницу или задачу они опираются.
    </p>;
  }
  return <p className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
    Урок создан без учебника — проверьте факты, определения и задачи. Чтобы урок опирался на книгу, привяжите тему к параграфу: <Link href="/dashboard/textbooks" className="font-semibold underline">Учебники → Темы КТП</Link>.
  </p>;
}

function generationModelLabel(value: unknown, options: { id: string; label: string }[] | undefined): string {
  if (!value || typeof value !== 'object') return '';
  const { provider, model } = value as { provider?: unknown; model?: unknown };
  if (typeof model !== 'string') return '';
  return options?.find(option => option.id === `${String(provider)}:${model}`)?.label || model;
}
