import type { KtpDraft, KtpSectionDraft, KtpTopicDraft } from '@/lib/api';

export type KtpDraftSummary = {
  sections: number;
  topics: number;
  hours: number;
  topicsWithoutObjectives: number;
};

export function summarizeKtpDraft(draft: KtpDraft): KtpDraftSummary {
  const topics = draft.sections.flatMap((section) => section.topics);
  return {
    sections: draft.sections.length,
    topics: topics.length,
    hours: topics.reduce((sum, topic) => sum + Math.max(0, Number(topic.hours) || 0), 0),
    topicsWithoutObjectives: topics.filter((topic) => !topic.learning_objectives.trim()).length,
  };
}

export function normalizeKtpDraft(draft: KtpDraft): KtpDraft {
  const sections = draft.sections
    .map((section) => {
      const topics = section.topics.filter((topic) => topic.name.trim()).map((topic) => ({
        ...topic,
        name: topic.name.trim(),
        hours: Math.max(1, Number(topic.hours) || 1),
        learning_objectives: topic.learning_objectives.trim(),
      }));
      return {
        ...section,
        name: section.name.trim(),
        topics,
        total_hours: topics.reduce((sum, topic) => sum + topic.hours, 0),
      };
    })
    .filter((section) => section.name && section.topics.length);
  const hours = sections.reduce((sum, section) => sum + section.total_hours, 0);
  return {
    ...draft,
    subject_name: draft.subject_name.trim(),
    grade: Number(draft.grade),
    hours_per_week: Number(draft.hours_per_week),
    hours_per_year: hours,
    sections,
  };
}

export function validateKtpDraft(draft: KtpDraft): string | null {
  if (!draft.subject_name.trim()) return 'Укажите предмет';
  if (draft.grade < 7 || draft.grade > 10) return 'Для этого шаблона выберите 7–10 класс';
  if (draft.hours_per_week <= 0) return 'Часов в неделю должно быть больше 0';
  if (!draft.sections.length) return 'В КТП нет разделов с темами';
  return null;
}

export function emptyTopic(index: number): KtpTopicDraft {
  return {
    ktp_number: String(index),
    name: '',
    hours: 1,
    lesson_type: 'study',
    learning_objectives: '',
    skills: [],
    resources: '',
  };
}

export function emptySection(index: number): KtpSectionDraft {
  return { name: `Раздел ${index}`, total_hours: 1, topics: [emptyTopic(1)] };
}
