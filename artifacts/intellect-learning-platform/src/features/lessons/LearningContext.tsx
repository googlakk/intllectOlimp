import { Link } from 'wouter';
import { useStudentLessonManifest, useCurriculumMap, type GeneratedLesson } from '@/lib/api';
import { assessmentQuestions } from './assessmentModel';
import { parseMathText } from '@/components/blocks/ShortExplanation';

export function LearningContext({ lesson, studentId, subjectId }: { lesson: GeneratedLesson; studentId: number; subjectId: string }) {
  const metadata = lesson.lesson_metadata;
  const type = metadata?.lesson_type;
  const sourceId = Number(metadata?.source_assessment_topic_id ?? 0);
  const source = useStudentLessonManifest(sourceId, studentId, type === 'reflection' && sourceId > 0);
  const curriculum = useCurriculumMap(studentId, Number(subjectId), type === 'review' || type === 'reflection');
  if (type !== 'review' && type !== 'reflection') return null;
  const sourceProgress = source.data?.progress;
  const hasResults = sourceProgress?.status === 'completed';
  const mistakes = hasResults && source.data?.lesson
    ? assessmentQuestions(source.data.lesson.blocks).filter(question => sourceProgress.answers[question.key] === false) : [];
  const covered = Array.isArray(metadata?.covered_topic_ids) ? metadata.covered_topic_ids : [];
  const weakTopics = curriculum.data?.topics.filter(topic => covered.includes(topic.id) && topic.mastery_status === 'needs_practice') ?? [];
  return <aside className="mx-auto mb-6 max-w-4xl space-y-3 rounded-xl border bg-card p-5">
    <h2 className="font-semibold">{type === 'reflection' ? 'Работа над вашими ошибками' : 'Что стоит закрепить'}</h2>
    {source.isLoading && <p>Загружаем результаты контрольной…</p>}
    {type === 'reflection' && !source.isLoading && !hasResults && <p>
      Можно пройти общий разбор ниже.{sourceId > 0 && !source.isError && <> Для разбора ваших ошибок сначала <Link href={`/learn/${subjectId}/${sourceId}`} className="text-primary underline">пройдите контрольную</Link>.</>}
    </p>}
    {hasResults && mistakes.length === 0 && <p>В сохранённой контрольной нет заданий с ошибками. Используйте этот урок для закрепления.</p>}
    {mistakes.map((question, index) => <details key={question.key} className="rounded-lg border p-3">
      <summary className="cursor-pointer font-medium">Разобрать ошибку {index + 1}: {parseMathText(question.prompt)}</summary>
      <p className="mt-3">Ваш ответ: {sourceProgress?.responses?.[question.key] ?? 'Ответ не сохранён в старой версии'}</p>
      <p>Правильный ответ: {parseMathText(question.correctAnswer)}</p>
      <div className="mt-2">{parseMathText(question.explanation)}</div>
    </details>)}
    {weakTopics.length > 0 ? <ul className="list-inside list-disc">{weakTopics.map(topic => <li key={topic.id}><Link href={`/learn/${subjectId}/${topic.id}`} className="text-primary underline">Повторить: {topic.name}</Link></li>)}</ul>
      : type === 'review' && <p>Повторите ключевые идеи и проверьте себя на новых заданиях.</p>}
  </aside>;
}
