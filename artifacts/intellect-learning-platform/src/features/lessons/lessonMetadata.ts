import type { GeneratedLesson, LearningObjective, TopicContract } from '@/lib/api/types';

export function lessonObjectives(lesson: GeneratedLesson | null | undefined): LearningObjective[] {
  const configured = lesson?.lesson_metadata?.objectives;
  return Array.isArray(configured) ? configured : [];
}

export function lessonHeaderText(lesson: GeneratedLesson | null | undefined) {
  return {
    learningObjective: String(lesson?.lesson_metadata?.learning_objectives || ''),
    topicTitle: String(lesson?.lesson_metadata?.topic_name || 'Урок'),
  };
}

const VOLUME_LABELS: Record<string, string> = {
  micro: 'маленькая тема',
  standard: 'стандартная тема',
  extended: 'расширенная тема',
  unit: 'модульная тема',
};

const SHAPE_LABELS: Record<string, string> = {
  micro_intro: 'короткое введение',
  standard_skill: 'стандартное освоение навыка',
  extended_concept: 'расширенное понятие',
  process_inquiry: 'исследование процесса',
  source_argument: 'источник и аргументация',
  procedure_mastery: 'отработка процедуры',
  project_or_practical: 'проектная/практическая работа',
  assessment_only: 'проверочный урок',
  unit_part: 'часть большого модуля',
};

export function lessonPlanningSummary(lesson: GeneratedLesson | null | undefined) {
  const contract = lesson?.lesson_metadata?.topic_contract as TopicContract | undefined;
  if (!contract) return null;
  const budget = contract.block_budget || lesson?.lesson_metadata?.block_budget || {};
  return {
    volume: contract.volume || '',
    volumeLabel: VOLUME_LABELS[String(contract.volume)] || String(contract.volume || 'тема'),
    shape: contract.lesson_shape || String(lesson?.lesson_metadata?.lesson_shape || ''),
    shapeLabel: SHAPE_LABELS[String(contract.lesson_shape || lesson?.lesson_metadata?.lesson_shape)] || String(contract.lesson_shape || lesson?.lesson_metadata?.lesson_shape || 'структура урока'),
    complexity: contract.complexity || '',
    objectiveCount: contract.objective_count || 0,
    mediaPolicy: contract.media_policy || 'optional',
    blockRange: typeof budget.min === 'number' && typeof budget.max === 'number'
      ? `${budget.min}-${budget.max}`
      : '',
    modulePart: contract.module_part_index && contract.module_total_parts
      ? `${contract.module_part_index}/${contract.module_total_parts}`
      : '',
  };
}
