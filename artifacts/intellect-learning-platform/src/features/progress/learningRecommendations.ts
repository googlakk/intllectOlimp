import type { CurriculumMapTopic } from '@/lib/api/types';

export function recommendLearning(topics: CurriculumMapTopic[]): { topic: CurriculumMapTopic; action: string; reason: string } | null {
  const published = topics.filter(topic => topic.lesson_status === 'published');
  const unfinished = published.find(topic => topic.progress_status === 'in_progress');
  if (unfinished) return { topic: unfinished, action: 'Продолжить урок', reason: 'Вы уже начали этот урок — продолжите с сохранённого места.' };
  const reflection = published.find(topic => topic.lesson_type === 'reflection' && topic.progress_status !== 'completed' && topics.some(source => source.id === topic.source_assessment_topic_id && source.progress_status === 'completed' && source.mastery_status === 'needs_practice'));
  if (reflection) return { topic: reflection, action: 'Разобрать ошибки', reason: 'Разбор поможет закрепить цели, вызвавшие затруднения в контрольной.' };
  const weak = published.find(topic => topic.mastery_status === 'needs_practice');
  if (weak) return { topic: weak, action: 'Повторить трудную тему', reason: 'По результатам проверки этим целям нужна дополнительная практика.' };
  const next = published.find(topic => topic.progress_status !== 'completed' && topic.state !== 'mastered');
  return next ? { topic: next, action: 'Начать следующий урок', reason: 'Следующая опубликованная тема вашей программы.' } : null;
}
