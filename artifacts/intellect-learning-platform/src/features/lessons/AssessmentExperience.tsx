import { useEffect, useRef, useState } from 'react';
import { Link } from 'wouter';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { saveProgress, useRestartLessonProgress, type GeneratedLesson, type ProgressRecord } from '@/lib/api';
import { parseMathText } from '@/components/blocks/ShortExplanation';
import { assessmentQuestions } from './assessmentModel';
import { applyProgressToCache } from './progressCache';
import { lessonHeaderText } from './lessonMetadata';

export function AssessmentExperience({ lesson, progress, studentId, subjectId, reload }: {
  lesson: GeneratedLesson; progress: ProgressRecord | null | undefined; studentId: number; subjectId: string;
  reload: () => Promise<unknown>;
}) {
  const queryClient = useQueryClient();
  const questions = assessmentQuestions(lesson.blocks);
  const [responses, setResponses] = useState<Record<string, string>>(progress?.responses ?? {});
  const [completed, setCompleted] = useState(progress?.status === 'completed');
  const [result, setResult] = useState<ProgressRecord | null>(progress ?? null);
  const started = useRef(Date.now());
  const restart = useRestartLessonProgress();
  const save = useMutation({ mutationFn: (finish: boolean) => saveProgress({
    student_id: studentId, topic_id: lesson.topic_id, lesson_version_id: lesson.active_version_id,
    status: finish ? 'completed' : 'in_progress', responses, answers: {},
    current_step: 0, max_opened_step: 0,
    elapsed_time_sec: Math.floor((Date.now() - started.current) / 1000),
    attempts_by_step: Object.fromEntries(lesson.blocks.map((_, index) => [String(index), 1])),
  }), onSuccess: async (saved, finish) => {
    applyProgressToCache(queryClient, saved);
    if (finish) { setCompleted(true); setResult(saved); }
    await queryClient.invalidateQueries({ queryKey: ['progress', studentId] });
    await queryClient.invalidateQueries({ queryKey: ['curriculum-map', studentId] });
    await queryClient.invalidateQueries({ queryKey: ['subjects'] });
  }});
  useEffect(() => {
    if (completed || Object.keys(responses).length === 0) return;
    const timer = window.setTimeout(() => { if (!save.isPending) save.mutate(false); }, 1200);
    return () => window.clearTimeout(timer);
  }, [responses, completed]);
  const answered = questions.filter(question => responses[question.key]?.trim()).length;
  const startAgain = async () => {
    try {
      await restart.mutateAsync({ studentId, topicId: lesson.topic_id });
      setResponses({}); setCompleted(false); setResult(null); started.current = Date.now();
      await reload();
    } catch { /* Mutation error remains visible with the completed result. */ }
  };
  return <div className="mx-auto max-w-3xl space-y-6 pb-12">
    <Link href={`/learn/${subjectId}`} className="text-primary">← Программа курса</Link>
    <h1 className="text-3xl font-bold">{lessonHeaderText(lesson).topicTitle}</h1>
    <p className="text-muted-foreground">{completed ? 'Контрольная завершена. Посмотрите объяснения и вернитесь к заданиям, вызвавшим трудности.' : 'Работайте в своём темпе. Ответы и объяснения появятся после сдачи всей работы.'}</p>
    {completed && <section className="rounded-xl border bg-card p-5" aria-live="polite">
      <h2 className="text-xl font-semibold">Результат: {result?.score ?? 0}%</h2>
      <p>Пройдено — не значит освоено: ошибки показывают, что стоит повторить.</p>
      <button disabled={restart.isPending} onClick={() => void startAgain()} className="mt-4 rounded-lg bg-primary px-4 py-2 text-primary-foreground">Новая попытка</button>
    </section>}
    {questions.length === 0 && <p role="alert">В этой контрольной пока нет доступных заданий. Сообщите учителю.</p>}
    {questions.map((question, index) => <fieldset key={question.key} disabled={completed || save.isPending} className="rounded-xl border bg-card p-5">
      <legend className="px-2 font-semibold">Задание {index + 1}</legend>
      <div className="mb-4 whitespace-pre-wrap">{parseMathText(question.prompt)}</div>
      {question.options.length ? <div className="space-y-2">{question.options.map((option, optionIndex) => <label key={optionIndex} className="flex items-center gap-3 rounded-lg border p-3">
        <input type="radio" name={question.key} value={option} checked={responses[question.key] === option} onChange={() => setResponses(current => ({ ...current, [question.key]: option }))} />{parseMathText(option)}
      </label>)}</div> : <label className="block">Ваш ответ<input value={responses[question.key] ?? ''} onChange={event => setResponses(current => ({ ...current, [question.key]: event.target.value }))} className="mt-2 block w-full rounded-lg border bg-background p-3" /></label>}
      {completed && <div className="mt-4 rounded-lg bg-muted p-4">
        <p className="font-semibold">{result?.answers[question.key] ? 'Верно' : 'Нужно повторить'}</p>
        <p>Правильный ответ: {parseMathText(question.correctAnswer)}</p>
        <div className="mt-2 whitespace-pre-wrap">{parseMathText(question.explanation)}</div>
      </div>}
    </fieldset>)}
    {(save.error || restart.error) && <p role="alert" className="text-destructive">{(save.error || restart.error)?.message}. Ответы остались на странице, попробуйте ещё раз.</p>}
    {save.error && !completed && <button disabled={save.isPending} onClick={() => save.mutate(false)} className="rounded-lg border px-4 py-2">Повторить сохранение</button>}
    {!completed && questions.length > 0 && <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-background p-4">
      <span aria-live="polite">{save.isPending ? 'Сохраняется…' : save.isSuccess ? 'Сохранено' : `Ответов: ${answered} из ${questions.length}`}</span>
      <button disabled={save.isPending || answered < questions.length} onClick={() => save.mutate(true)} className="rounded-lg bg-primary px-5 py-3 text-primary-foreground disabled:opacity-50">Сдать работу</button>
    </div>}
  </div>;
}
