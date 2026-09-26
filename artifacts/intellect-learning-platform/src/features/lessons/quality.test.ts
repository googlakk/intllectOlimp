import { describe, expect, it } from 'vitest';
import type { Block, GeneratedLesson, LearningObjective } from '@/lib/api/types';
import { buildCoverage, getLessonQualityState, groupedMessages } from './quality';

const objectives: LearningObjective[] = [
  { id: 'o1', text: 'Understand proportional relationships' },
  { id: 'o2', text: 'Apply proportional relationships' },
];

const lessonBase: GeneratedLesson = {
  id: 1,
  topic_id: 10,
  blocks: [],
  lesson_metadata: { objectives },
  status: 'draft',
  generated_at: '2026-09-21T00:00:00Z',
  published_at: null,
  published_by: null,
  model_used: 'test',
};

describe('lesson quality helpers', () => {
  it('groups repeated quality messages by code', () => {
    expect(groupedMessages([
      { code: 'missing_practice', message: 'Нет практики' },
      { code: 'missing_practice', message: 'Нет практики' },
      { code: 'weak_intro', message: 'Слабое объяснение' },
    ])).toEqual(['Нет практики (2 блоков)', 'Слабое объяснение']);
  });

  it('builds fallback coverage from block categories when no report exists', () => {
    const blocks: Block[] = [
      { component: 'ShortExplanation', content: { objective_ids: ['o1'] } },
      { component: 'GuidedPractice', content: { objective_ids: ['o1'] } },
      { component: 'MasteryCheck', content: { objective_ids: ['o1'] } },
      { component: 'ShortExplanation', content: { objective_ids: ['o2'] } },
    ];

    expect(buildCoverage(objectives, blocks, undefined)).toEqual([
      { objective: objectives[0], explanation: true, practice: true, assessment: true },
      { objective: objectives[1], explanation: true, practice: false, assessment: false },
    ]);
  });

  it('does not treat guided practice alone as objective assessment coverage', () => {
    const blocks: Block[] = [
      { component: 'GuidedPractice', content: { objective_ids: ['o1'] } },
    ];

    expect(buildCoverage(objectives.slice(0, 1), blocks, undefined)).toEqual([
      { objective: objectives[0], explanation: false, practice: true, assessment: false },
    ]);
  });

  it('prevents publishing when quality report marks a lesson as not publishable', () => {
    const state = getLessonQualityState({
      ...lessonBase,
      blocks: [{ component: 'ShortExplanation', content: { objective_ids: ['o1'] } }],
      lesson_metadata: {
        objectives,
        quality_report: {
          publishable: false,
          errors: [{ code: 'missing_assessment', message: 'Нет проверки' }],
          gaps: [{ objective_id: 'o2', missing: ['practice', 'assessment'] }],
          warnings: [{ code: 'style', message: 'Слишком длинный текст' }],
        },
      },
    }, true);

    expect(state.hasObjectiveContract).toBe(true);
    expect(state.canPublish).toBe(false);
    expect(state.blockingIssues).toEqual([
      'Перед публикацией исправьте отмеченные недочёты',
      'Нет проверки',
      'Не покрыта цель: o2 (практика, проверка)',
    ]);
    expect(state.warningMessages).toEqual(['Слишком длинный текст']);
  });

  it('allows publishing only after warnings are acknowledged', () => {
    const lesson: GeneratedLesson = {
      ...lessonBase,
      blocks: [{ component: 'ShortExplanation', content: { objective_ids: ['o1'] } }],
      lesson_metadata: {
        objectives,
        quality_report: {
          publishable: true,
          warnings: [{ code: 'minor', message: 'Можно усилить пример' }],
        },
      },
    };

    expect(getLessonQualityState(lesson, false).canPublish).toBe(false);
    expect(getLessonQualityState(lesson, true).canPublish).toBe(true);
  });

  it('requires legacy lessons to be reviewed before publishing', () => {
    const state = getLessonQualityState({
      ...lessonBase,
      blocks: [{ component: 'ShortExplanation', content: {} }],
      lesson_metadata: {},
    }, false);

    expect(state.hasObjectiveContract).toBe(false);
    expect(state.canPublish).toBe(false);
    expect(state.blockingIssues).toEqual(['Старый урок нужно проверить или перегенерировать перед публикацией']);
  });
});

describe('publishing over soft errors', () => {
  const lesson = (report: Record<string, unknown>) => ({
    blocks: [{ component: 'ShortExplanation', content: {} }],
    lesson_metadata: { objectives: [{ id: 'obj-1', text: 'Цель' }], quality_report: { errors: [{ code: 'step_solver_invalid', message: 'Решаю по шагам: …' }], gaps: [], warnings: [], ...report } },
  }) as unknown as Parameters<typeof getLessonQualityState>[0];

  it('allows publishing after the teacher confirms soft errors', () => {
    const soft = lesson({ publishable: false, overridable: true });
    expect(getLessonQualityState(soft, false).canOverride).toBe(true);
    expect(getLessonQualityState(soft, false).canPublish).toBe(false);
    expect(getLessonQualityState(soft, false, true).canPublish).toBe(true);
  });

  it('lets the teacher confirm all errors, including old reports without the flag', () => {
    const old = lesson({ publishable: false });
    expect(getLessonQualityState(old, false, true).canPublish).toBe(true);
  });
});
