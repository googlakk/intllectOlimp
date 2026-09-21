import { describe, expect, it } from 'vitest';
import type { Block, LearningObjective, ObjectiveMastery } from '@/lib/api/types';
import {
  buildActiveLessonRoute,
  calculateDiagnosticCompletion,
  calculateLessonCompletion,
  isAssessmentBlock,
  isDiagnosticFinished,
} from './studentProgress';

const objectives: LearningObjective[] = [
  { id: 'o1', text: 'Explain linear equations' },
  { id: 'o2', text: 'Solve linear equations' },
];

const blocks: Block[] = [
  { component: 'RetrievalCheck', content: { evidence_stage: 'diagnostic', objective_ids: ['o1'] } },
  { component: 'RetrievalCheck', content: { evidence_stage: 'diagnostic', objective_ids: ['o2'] } },
  { component: 'ShortExplanation', content: { objective_ids: ['o1'] } },
  { component: 'GuidedPractice', content: { objective_ids: ['o2'] } },
  { component: 'IndependentProblem', content: { evidence_stage: 'assessment', objective_ids: ['o1'] } },
  {
    component: 'MasteryCheck',
    content: {
      evidence_stage: 'assessment',
      questions: [
        { objective_ids: ['o1'] },
        { dimension: 'o2' },
      ],
    },
  },
];

describe('studentProgress route building', () => {
  it('shows only diagnostic blocks before the diagnostic phase is complete', () => {
    const route = buildActiveLessonRoute(blocks, objectives, false, {});

    expect(route.hasObjectiveRoute).toBe(true);
    expect(route.diagnosticOriginalIndices).toEqual([0, 1]);
    expect(route.activeOriginalIndices).toEqual([0, 1]);
    expect(route.activeBlocks.map((block) => block.component)).toEqual(['RetrievalCheck', 'RetrievalCheck']);
  });

  it('skips non-assessment blocks for objectives that passed diagnostics', () => {
    const mastery: Record<string, ObjectiveMastery> = {
      o1: { status: 'in_progress', diagnostic_passed: true },
      o2: { status: 'needs_practice', diagnostic_passed: false },
    };

    const route = buildActiveLessonRoute(blocks, objectives, true, mastery);

    expect(route.activeOriginalIndices).toEqual([3, 4, 5]);
    expect(route.activeBlocks.map((block) => block.component)).toEqual([
      'GuidedPractice',
      'IndependentProblem',
      'MasteryCheck',
    ]);
  });
});

describe('studentProgress completion calculations', () => {
  it('classifies assessment blocks without depending on block rendering components', () => {
    expect(isAssessmentBlock({ component: 'MasteryCheck', content: {} })).toBe(true);
    expect(isAssessmentBlock({ component: 'IndependentProblem', content: {} })).toBe(true);
    expect(isAssessmentBlock({ component: 'ShortExplanation', content: {} })).toBe(false);
  });

  it('calculates final score, objective mastery, and merged evidence', () => {
    const result = calculateLessonCompletion({
      activeBlocks: [blocks[4], blocks[5]],
      activeOriginalIndices: [4, 5],
      objectives,
      answers: {
        4: true,
        '5_q0': true,
        '5_q1': false,
      },
      attemptsByStep: { 4: 2, 5: 1 },
      currentMastery: {
        o1: { status: 'in_progress', diagnostic_passed: true },
        o2: { status: 'needs_practice', diagnostic_passed: false },
      },
      savedObjectiveEvidence: {
        o1: [{ objective_id: 'o1', block_index: 0, stage: 'diagnostic', correct: true, attempts: 1 }],
      },
    });

    expect(result.score).toBe(67);
    expect(result.level).toBe('Уверенный');
    expect(result.masteryStatus).toBe('needs_practice');
    expect(result.mastery.o1).toMatchObject({
      status: 'mastered',
      score: 100,
      diagnostic_passed: true,
      final_passed: true,
    });
    expect(result.mastery.o2).toMatchObject({
      status: 'needs_practice',
      score: 0,
      diagnostic_passed: false,
      final_passed: false,
    });
    expect(result.evidence.o1).toEqual([
      { objective_id: 'o1', block_index: 0, stage: 'diagnostic', correct: true, attempts: 1 },
      { objective_id: 'o1', block_index: 4, stage: 'assessment', correct: true, attempts: 2 },
      { objective_id: 'o1', block_index: 5, stage: 'assessment', correct: true, attempts: 1 },
    ]);
    expect(result.evidence.o2).toEqual([
      { objective_id: 'o2', block_index: 5, stage: 'assessment', correct: false, attempts: 1 },
    ]);
  });

  it('calculates diagnostic mastery from single-block and question-level answers', () => {
    const result = calculateDiagnosticCompletion({
      blocks,
      diagnosticOriginalIndices: [0, 1],
      objectives,
      answers: {
        0: true,
        '1_q0': true,
        '1_q1': false,
      },
      attemptsByStep: { 0: 1, 1: 3 },
    });

    expect(result.mastery.o1).toMatchObject({
      status: 'in_progress',
      score: 100,
      diagnostic_passed: true,
      final_passed: false,
    });
    expect(result.mastery.o2).toMatchObject({
      status: 'needs_practice',
      score: 50,
      diagnostic_passed: false,
      final_passed: false,
    });
    expect(result.evidence.o2).toEqual([
      { objective_id: 'o2', block_index: 1, stage: 'diagnostic', correct: true, attempts: 3 },
      { objective_id: 'o2', block_index: 1, stage: 'diagnostic', correct: false, attempts: 3 },
    ]);
  });

  it('detects whether all diagnostic blocks already have persisted answers', () => {
    expect(isDiagnosticFinished([0, 1], { 0: true, '1_q0': false })).toBe(true);
    expect(isDiagnosticFinished([0, 1], { 0: true })).toBe(false);
    expect(isDiagnosticFinished([], { 0: true })).toBe(false);
  });
});
