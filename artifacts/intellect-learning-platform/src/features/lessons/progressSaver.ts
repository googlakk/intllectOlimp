import { useCallback, type Dispatch, type RefObject, type SetStateAction } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useSaveProgress,
  type MasteryStatus,
  type ObjectiveEvidence,
  type ObjectiveMastery,
} from '@/lib/api';
import type { AttemptsByStep, LessonAnswers } from './studentProgress';
import { completedLessonInvalidationKeys, lessonProgressQueryKey } from './progressCache';
import { buildSaveProgressInput } from './progressPersistence';

export type SaveLessonProgress = (
  step: number,
  maxStep: number,
  status: 'in_progress' | 'completed',
  answers: LessonAnswers,
  attemptsByStep: AttemptsByStep,
  finalScore?: number,
  finalLevel?: string,
  mastery?: Record<string, ObjectiveMastery>,
  evidence?: Record<string, ObjectiveEvidence[]>,
  masteryStatus?: MasteryStatus,
) => void;

export function useLessonProgressSaver(params: {
  baseElapsedTime: RefObject<number>;
  setObjectiveMastery: Dispatch<SetStateAction<Record<string, ObjectiveMastery>>>;
  setSavedObjectiveEvidence: Dispatch<SetStateAction<Record<string, ObjectiveEvidence[]>>>;
  startTime: RefObject<number>;
  studentId: number | undefined;
  topicId: number;
}) {
  const {
    baseElapsedTime,
    setObjectiveMastery,
    setSavedObjectiveEvidence,
    startTime,
    studentId,
    topicId,
  } = params;
  const saveProgressMutation = useSaveProgress();
  const queryClient = useQueryClient();

  const saveState: SaveLessonProgress = useCallback((
    step,
    maxStep,
    status,
    answers,
    attemptsByStep,
    finalScore,
    finalLevel,
    mastery,
    evidence,
    masteryStatus,
  ) => {
    if (!studentId) return;
    const elapsedTimeSec = baseElapsedTime.current + Math.round((Date.now() - startTime.current) / 1000);

    saveProgressMutation.mutate(buildSaveProgressInput({
      studentId,
      topicId,
      status,
      step,
      maxStep,
      answers,
      attemptsByStep,
      elapsedTimeSec,
      finalScore,
      finalLevel,
      mastery,
      objectiveEvidence: evidence,
      masteryStatus,
    }), {
      onSuccess: (data) => {
        queryClient.setQueryData(lessonProgressQueryKey(studentId, topicId), data);
        if (status === 'completed') {
          setObjectiveMastery(data.objective_mastery || {});
          setSavedObjectiveEvidence(data.objective_evidence || {});
          completedLessonInvalidationKeys().forEach((queryKey) => {
            queryClient.invalidateQueries({ queryKey });
          });
        }
      },
    });
  }, [
    baseElapsedTime,
    queryClient,
    saveProgressMutation,
    setObjectiveMastery,
    setSavedObjectiveEvidence,
    startTime,
    studentId,
    topicId,
  ]);

  return {
    saveError: saveProgressMutation.error as Error | null,
    saveState,
  };
}
