import type { Block } from './api/types';

const ASSESSMENT_COMPONENTS = new Set([
  'ErrorHunt', 'LearningPath',
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
  'StepSolver',
  'FunctionExplorer',
  'RuleDiscovery',
  'TransformationMachine',
  'MasteryCheck',
]);

const OBJECTIVE_ASSESSMENT_COMPONENTS = new Set([
  'ErrorHunt', 'LearningPath',
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
  'StepSolver',
  'FunctionExplorer',
  'RuleDiscovery',
  'TransformationMachine',
  'MasteryCheck',
]);

export function isAssessmentBlock(block: Block): boolean {
  return ASSESSMENT_COMPONENTS.has(block.component);
}

export function isObjectiveAssessmentBlock(block: Block): boolean {
  return OBJECTIVE_ASSESSMENT_COMPONENTS.has(block.component);
}
