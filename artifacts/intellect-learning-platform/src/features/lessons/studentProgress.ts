import type {
  Block,
  LearningObjective,
  MasteryStatus,
  ObjectiveEvidence,
  ObjectiveMastery,
} from '@/lib/api/types';
import { isAssessmentBlock } from '@/lib/lessonBlocks';

export { isAssessmentBlock };

export type LessonAnswers = Record<string | number, boolean>;
export type AttemptsByStep = Record<number, number>;

export type ActiveLessonRoute = {
  activeBlocks: Block[];
  activeOriginalIndices: number[];
  diagnosticOriginalIndices: number[];
  hasObjectiveRoute: boolean;
};

export type LessonCompletionResult = {
  score: number;
  level: string;
  mastery: Record<string, ObjectiveMastery>;
  evidence: Record<string, ObjectiveEvidence[]>;
  masteryStatus: MasteryStatus;
};

export type DiagnosticCompletionResult = {
  mastery: Record<string, ObjectiveMastery>;
  evidence: Record<string, ObjectiveEvidence[]>;
};

export function objectiveIdsForBlock(block: Block): string[] {
  const value = block.content?.objective_ids;
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string');
  if (typeof value === 'string') return [value];
  return [];
}

export function stageForBlock(block: Block): string | undefined {
  const stage = block.content?.evidence_stage;
  return typeof stage === 'string' ? stage : undefined;
}

export function getDiagnosticOriginalIndices(blocks: Block[]): number[] {
  return blocks
    .map((block, index) => ({ block, index }))
    .filter(({ block }) => stageForBlock(block) === 'diagnostic')
    .map(({ index }) => index);
}

export function buildActiveLessonRoute(
  blocks: Block[],
  objectives: LearningObjective[],
  diagnosticComplete: boolean,
  _objectiveMastery: Record<string, ObjectiveMastery>,
): ActiveLessonRoute {
  const diagnosticOriginalIndices = getDiagnosticOriginalIndices(blocks);
  const hasObjectiveRoute = objectives.length > 0 && diagnosticOriginalIndices.length > 0;

  if (!hasObjectiveRoute) {
    return {
      activeBlocks: blocks,
      activeOriginalIndices: blocks.map((_, index) => index),
      diagnosticOriginalIndices,
      hasObjectiveRoute,
    };
  }

  if (!diagnosticComplete) {
    return {
      activeBlocks: diagnosticOriginalIndices.map((index) => blocks[index]),
      activeOriginalIndices: diagnosticOriginalIndices,
      diagnosticOriginalIndices,
      hasObjectiveRoute,
    };
  }

  const activeOriginalIndices = blocks
    .map((block, index) => ({ block, index }))
    .filter(({ block }) => stageForBlock(block) !== 'diagnostic')
    .map(({ index }) => index);

  return {
    activeBlocks: activeOriginalIndices.map((index) => blocks[index]),
    activeOriginalIndices,
    diagnosticOriginalIndices,
    hasObjectiveRoute,
  };
}

export function calculateLessonCompletion(params: {
  activeBlocks: Block[];
  activeOriginalIndices: number[];
  objectives: LearningObjective[];
  answers: LessonAnswers;
  attemptsByStep: AttemptsByStep;
  currentMastery: Record<string, ObjectiveMastery>;
  savedObjectiveEvidence: Record<string, ObjectiveEvidence[]>;
}): LessonCompletionResult {
  const {
    activeBlocks,
    activeOriginalIndices,
    objectives,
    answers,
    attemptsByStep,
    currentMastery,
    savedObjectiveEvidence,
  } = params;

  const finalAnswerKeys = activeBlocks.flatMap((block, activeIndex) => {
    const originalIndex = activeOriginalIndices[activeIndex];
    if (stageForBlock(block) === 'diagnostic') return [];
    if (block.component === 'MasteryCheck') {
      const questions = Array.isArray(block.content.questions) ? block.content.questions : [];
      return questions.map((_, questionIndex) => `${originalIndex}_q${questionIndex}`);
    }
    return isAssessmentBlock(block) ? [String(originalIndex)] : [];
  });
  const answeredFinalKeys = finalAnswerKeys.filter((key) => answers[key] !== undefined);

  let score = 0;
  let level = 'Начинающий';
  if (finalAnswerKeys.length > 0) {
    const correctCount = answeredFinalKeys.filter((key) => answers[key] === true).length;
    score = Math.round((correctCount / finalAnswerKeys.length) * 100);
    if (score >= 86) level = 'Мастер';
    else if (score >= 66) level = 'Уверенный';
    else if (score >= 41) level = 'Развивающийся';
  } else {
    level = 'Не оценено';
  }

  const mastery: Record<string, ObjectiveMastery> = {};
  const evidence: Record<string, ObjectiveEvidence[]> = {};
  objectives.forEach((objective) => {
    const answersForObjective = activeBlocks.flatMap((block, activeIndex) => {
      const originalIndex = activeOriginalIndices[activeIndex];
      if (stageForBlock(block) === 'diagnostic') return [];
      if (block.component === 'MasteryCheck') {
        const questions = Array.isArray(block.content.questions)
          ? block.content.questions as Array<Record<string, unknown>>
          : [];
        return questions.flatMap((question, questionIndex) => {
          const rawIds = question.objective_ids;
          const questionIds = Array.isArray(rawIds)
            ? rawIds.filter((id): id is string => typeof id === 'string')
            : typeof rawIds === 'string' ? [rawIds] : [];
          const matches = questionIds.includes(objective.id) || question.dimension === objective.id;
          const key = `${originalIndex}_q${questionIndex}`;
          return matches && answers[key] !== undefined
            ? [{ key, blockIndex: originalIndex, correct: answers[key] === true }]
            : [];
        });
      }
      const isFinalAssessment = stageForBlock(block) === 'assessment'
        && isAssessmentBlock(block)
        && objectiveIdsForBlock(block).includes(objective.id);
      const key = String(originalIndex);
      return isFinalAssessment && answers[key] !== undefined
        ? [{ key, blockIndex: originalIndex, correct: answers[key] === true }]
        : [];
    });
    const objectiveScore = answersForObjective.length
      ? Math.round(answersForObjective.filter((item) => item.correct).length / answersForObjective.length * 100)
      : 0;
    const diagnosticPassed = currentMastery[objective.id]?.diagnostic_passed === true;
    const mastered = answersForObjective.length > 0
      && objectiveScore >= 80
      && answersForObjective.some((item) => item.correct);
    const status: MasteryStatus = mastered
      ? 'mastered'
      : (answersForObjective.length ? 'needs_practice' : (diagnosticPassed ? 'in_progress' : 'not_assessed'));
    const objectiveEvidence = answersForObjective.map(({ blockIndex, correct }) => ({
      objective_id: objective.id,
      correct,
      attempts: attemptsByStep[blockIndex] || 1,
      block_index: blockIndex,
      stage: 'assessment',
    }));
    mastery[objective.id] = {
      status,
      score: objectiveScore,
      diagnostic_passed: diagnosticPassed,
      final_passed: mastered,
    };
    evidence[objective.id] = [...(savedObjectiveEvidence[objective.id] || []), ...objectiveEvidence];
  });

  const masteredCount = Object.values(mastery).filter((item) => item.status === 'mastered').length;
  const masteryStatus: MasteryStatus = objectives.length === 0
    ? 'not_assessed'
    : (masteredCount === objectives.length ? 'mastered' : 'needs_practice');

  return { score, level, mastery, evidence, masteryStatus };
}

export function calculateDiagnosticCompletion(params: {
  blocks: Block[];
  diagnosticOriginalIndices: number[];
  objectives: LearningObjective[];
  answers: LessonAnswers;
  attemptsByStep: AttemptsByStep;
}): DiagnosticCompletionResult {
  const { blocks, diagnosticOriginalIndices, objectives, answers, attemptsByStep } = params;
  const mastery: Record<string, ObjectiveMastery> = {};
  const evidence: Record<string, ObjectiveEvidence[]> = {};

  objectives.forEach((objective) => {
    const related = diagnosticOriginalIndices
      .filter((originalIndex) => objectiveIdsForBlock(blocks[originalIndex]).includes(objective.id));
    const objectiveEvidence = related.flatMap((originalIndex) => {
      const questionAnswers = Object.entries(answers)
        .filter(([key]) => key.startsWith(`${originalIndex}_q`))
        .map(([, correct]) => ({ correct }));
      if (questionAnswers.length > 0) {
        return questionAnswers.map(({ correct }) => ({
          objective_id: objective.id,
          block_index: originalIndex,
          stage: 'diagnostic',
          correct,
          attempts: attemptsByStep[originalIndex] || 1,
        }));
      }
      return answers[originalIndex] === undefined
        ? []
        : [{
          objective_id: objective.id,
          block_index: originalIndex,
          stage: 'diagnostic',
          correct: answers[originalIndex] === true,
          attempts: attemptsByStep[originalIndex] || 1,
        }];
    });
    const score = objectiveEvidence.length
      ? Math.round(objectiveEvidence.filter((item) => item.correct).length / objectiveEvidence.length * 100)
      : 0;
    const passed = objectiveEvidence.length > 0 && score >= 80;
    mastery[objective.id] = {
      status: passed ? 'in_progress' : 'needs_practice',
      score,
      diagnostic_passed: passed,
      final_passed: false,
    };
    evidence[objective.id] = objectiveEvidence;
  });

  return { mastery, evidence };
}

export function isDiagnosticFinished(
  diagnosticOriginalIndices: number[],
  answers: LessonAnswers | undefined,
): boolean {
  const savedAnswers = answers || {};
  return diagnosticOriginalIndices.length > 0 && diagnosticOriginalIndices.every((index) => (
    savedAnswers[String(index)] !== undefined
    || Object.keys(savedAnswers).some((key) => key.startsWith(`${index}_q`))
  ));
}

export function shouldReopenCompletedProgress(params: {
  activeBlocksLength: number;
  isCompleted: boolean;
  maxOpenedStep: number;
}): boolean {
  const { activeBlocksLength, isCompleted, maxOpenedStep } = params;
  return isCompleted && activeBlocksLength > 0 && maxOpenedStep < activeBlocksLength - 1;
}
