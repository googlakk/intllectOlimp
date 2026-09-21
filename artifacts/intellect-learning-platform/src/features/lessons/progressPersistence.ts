import type {
  MasteryStatus,
  ObjectiveEvidence,
  ObjectiveMastery,
  SaveProgressInput,
} from '@/lib/api';
import type { AttemptsByStep, LessonAnswers } from './studentProgress';

export type BuildSaveProgressInputParams = {
  answers: LessonAnswers;
  attemptsByStep: AttemptsByStep;
  elapsedTimeSec: number;
  finalLevel?: string;
  finalScore?: number;
  mastery?: Record<string, ObjectiveMastery>;
  masteryStatus?: MasteryStatus;
  maxStep: number;
  objectiveEvidence?: Record<string, ObjectiveEvidence[]>;
  status: 'in_progress' | 'completed';
  step: number;
  studentId: number;
  topicId: number;
};

export function buildSaveProgressInput(params: BuildSaveProgressInputParams): SaveProgressInput {
  const {
    answers,
    attemptsByStep,
    elapsedTimeSec,
    finalLevel,
    finalScore,
    mastery,
    masteryStatus,
    maxStep,
    objectiveEvidence,
    status,
    step,
    studentId,
    topicId,
  } = params;

  return {
    student_id: studentId,
    topic_id: topicId,
    status,
    current_step: step,
    max_opened_step: maxStep,
    answers,
    attempts_by_step: attemptsByStep,
    time_spent_sec: elapsedTimeSec,
    elapsed_time_sec: elapsedTimeSec,
    ...(finalScore !== undefined ? { score: finalScore, mastery_level: finalLevel } : {}),
    ...(mastery ? { objective_mastery: mastery } : {}),
    ...(objectiveEvidence ? { objective_evidence: objectiveEvidence } : {}),
    ...(masteryStatus ? { mastery_status: masteryStatus } : {}),
  };
}
