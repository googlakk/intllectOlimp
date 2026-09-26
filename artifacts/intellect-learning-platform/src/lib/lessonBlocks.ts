import type { Block } from './api/types';

const ASSESSMENT_COMPONENTS = new Set([
  'GuidedPractice',
  'IndependentProblem',
  'RetrievalCheck',
  'TextEvidencePicker',
  'ArgumentBuilder',
  'SortAndClassify',
  'ProcessBuilder',
  'ArgumentMap',
  'BranchingScenario',
  'MisconceptionDebugger',
  'PredictionLab',
  'DataInvestigation',
  'PhysicsSandbox',
  'HotspotInvestigation',
  'CodeBlocksLab',
  'ChronologyLine',
  'CauseEffectMap',
  'MasteryCheck',
]);

const OBJECTIVE_ASSESSMENT_COMPONENTS = new Set([
  'IndependentProblem',
  'RetrievalCheck',
  'TextEvidencePicker',
  'ArgumentBuilder',
  'SortAndClassify',
  'ProcessBuilder',
  'ArgumentMap',
  'BranchingScenario',
  'MisconceptionDebugger',
  'PredictionLab',
  'DataInvestigation',
  'PhysicsSandbox',
  'HotspotInvestigation',
  'CodeBlocksLab',
  'ChronologyLine',
  'CauseEffectMap',
  'MasteryCheck',
]);

export function isAssessmentBlock(block: Block): boolean {
  return ASSESSMENT_COMPONENTS.has(block.component);
}

export function isObjectiveAssessmentBlock(block: Block): boolean {
  return OBJECTIVE_ASSESSMENT_COMPONENTS.has(block.component);
}
