import type { SectionOutline } from '@/lib/api/types';

export function catalogLessonChoices(sections: SectionOutline[] | undefined, query: string) {
  const normalized = query.trim().toLocaleLowerCase('ru-RU');
  return (sections ?? []).flatMap((section) => section.topics
    .filter((topic) => !topic.archived_at && typeof topic.lesson_id === 'number' && topic.lesson_id > 0)
    .filter((topic) => `${topic.ktp_number ?? ''} ${topic.name} ${section.name}`.toLocaleLowerCase('ru-RU').includes(normalized))
    .map((topic) => ({ topic, sectionName: section.name })));
}

export function componentLessonPath(topicId: number, componentId: string): string {
  return `/dashboard/lessons/${topicId}?add_component=${encodeURIComponent(componentId)}`;
}
