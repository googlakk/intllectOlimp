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
  lessonVersionId?: number | null;
  currentEpisodeId?: string | null;
  currentSceneId?: string | null;
  avatarEnabled?: boolean;
  audioEnabled?: boolean;
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
    lessonVersionId,
    currentEpisodeId,
    currentSceneId,
    avatarEnabled,
    audioEnabled,
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
    ...(lessonVersionId ? { lesson_version_id: lessonVersionId } : {}),
    ...(currentEpisodeId ? { current_episode_id: currentEpisodeId } : {}),
    ...(currentSceneId ? { current_scene_id: currentSceneId } : {}),
    ...(avatarEnabled !== undefined ? { avatar_enabled: avatarEnabled } : {}),
    ...(audioEnabled !== undefined ? { audio_enabled: audioEnabled } : {}),
    ...(finalScore !== undefined ? { score: finalScore, mastery_level: finalLevel } : {}),
    ...(mastery ? { objective_mastery: mastery } : {}),
    ...(objectiveEvidence ? { objective_evidence: objectiveEvidence } : {}),
    ...(masteryStatus ? { mastery_status: masteryStatus } : {}),
  };
}
