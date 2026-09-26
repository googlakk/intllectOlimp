import type { Block, GeneratedLesson, LearningObjective, QualityReport } from '@/lib/api/types';
import { isObjectiveAssessmentBlock } from '@/lib/lessonBlocks';

const STAGE_LABELS: Record<string, string> = { explanation: 'объяснение', practice: 'практика', assessment: 'проверка', diagnostic: 'стартовая проверка' };

const EXPLANATION_COMPONENTS = [
  'ShortExplanation',
  'KeyConcept',
  'WorkedExample',
  'Presentation',
  'Illustration',
  'GeneratedMedia',
  'MindMap',
  'Timeline',
  'PredictionLab',
  'HotspotInvestigation',
];

const PRACTICE_COMPONENTS = [
  'GuidedPractice',
  'IndependentProblem',
  'RetrievalCheck',
  'TextEvidencePicker',
  'ArgumentBuilder',
  'InteractiveGraph',
  'SortAndClassify',
  'ProcessBuilder',
  'ArgumentMap',
  'BranchingScenario',
  'MisconceptionDebugger',
  'DataInvestigation',
  'PhysicsSandbox',
  'CodeBlocksLab',
  'ChronologyLine',
  'CauseEffectMap',
  'StepSolver',
  'FunctionExplorer',
];

export type ObjectiveCoverage = {
  objective: LearningObjective;
  explanation: boolean;
  practice: boolean;
  assessment: boolean;
};

export type LessonQualityState = {
  objectives: LearningObjective[];
  qualityReport: QualityReport | undefined;
  hasObjectiveContract: boolean;
  coverage: ObjectiveCoverage[];
  blockingIssues: string[];
  warningMessages: string[];
  canPublish: boolean;
};

export function objectiveIdsForBlock(block: Block): string[] {
  const ids = block.content?.objective_ids;
  if (Array.isArray(ids)) return ids.filter((id): id is string => typeof id === 'string');
  return typeof ids === 'string' ? [ids] : [];
}

export function qualityMessage(item: unknown): string {
  if (typeof item === 'string') return item;
  if (item && typeof item === 'object') {
    const value = item as Record<string, unknown>;
    return String(value.message || value.detail || value.code || JSON.stringify(item));
  }
  return String(item);
}

export function groupedMessages(items: unknown[] = []): string[] {
  const groups = new Map<string, { message: string; count: number }>();
  items.forEach((item) => {
    const message = qualityMessage(item);
    const code = item && typeof item === 'object'
      ? String((item as Record<string, unknown>).code || message)
      : message;
    const current = groups.get(code);
    groups.set(code, { message, count: (current?.count || 0) + 1 });
  });
  return Array.from(groups.values()).map(({ message, count }) => (
    count > 1 ? `${message} (${count} блоков)` : message
  ));
}

export function buildCoverage(
  objectives: LearningObjective[],
  blocks: Block[],
  qualityReport: QualityReport | undefined,
): ObjectiveCoverage[] {
  return objectives.map((objective) => {
    const related = blocks.filter((block) => objectiveIdsForBlock(block).includes(objective.id));
    const report = qualityReport?.objectives?.[objective.id];
    return {
      objective,
      explanation: report
        ? (report.explanation?.length || 0) > 0
        : related.some((block) => EXPLANATION_COMPONENTS.includes(block.component)),
      practice: report
        ? (report.practice?.length || 0) > 0
        : related.some((block) => PRACTICE_COMPONENTS.includes(block.component)),
      assessment: report
        ? (report.assessment?.length || 0) > 0
        : related.some(isObjectiveAssessmentBlock),
    };
  });
}

export function buildBlockingIssues(
  qualityReport: QualityReport | undefined,
  hasObjectiveContract: boolean,
  blockCount: number,
): string[] {
  return [
    ...(qualityReport?.publishable === false ? ['Перед публикацией исправьте отмеченные недочёты'] : []),
    ...groupedMessages(qualityReport?.errors || []),
    ...(qualityReport?.gaps || []).map((gap) => (
      typeof gap === 'string'
        ? `Не покрыта цель: ${gap}`
        : `Не покрыта цель: ${gap.objective || gap.objective_id || 'неизвестная цель'} (${(gap.missing || []).map(stage => STAGE_LABELS[stage] ?? stage).join(', ')})`
    )),
    ...(!hasObjectiveContract && blockCount > 0 ? ['Старый урок нужно проверить или перегенерировать перед публикацией'] : []),
    ...(hasObjectiveContract && !qualityReport ? ['Для нового урока отсутствует отчёт проверки качества'] : []),
  ];
}

export function getLessonQualityState(
  lesson: GeneratedLesson | null | undefined,
  warningsAcknowledged: boolean,
): LessonQualityState {
  const blocks = lesson?.blocks || [];
  const metadata = lesson?.lesson_metadata;
  const objectives = metadata?.objectives || [];
  const qualityReport = metadata?.quality_report;
  const hasObjectiveContract = objectives.length > 0 || Boolean(qualityReport);
  const coverage = buildCoverage(objectives, blocks, qualityReport);
  const blockingIssues = buildBlockingIssues(qualityReport, hasObjectiveContract, blocks.length);
  const warningMessages = groupedMessages(qualityReport?.warnings || []);
  const canPublish = blockingIssues.length === 0 && (warningMessages.length === 0 || warningsAcknowledged);

  return {
    objectives,
    qualityReport,
    hasObjectiveContract,
    coverage,
    blockingIssues,
    warningMessages,
    canPublish,
  };
}
