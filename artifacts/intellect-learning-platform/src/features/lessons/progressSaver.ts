import { useCallback, useEffect, useRef, type Dispatch, type RefObject, type SetStateAction } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  useSaveProgress,
  type ProgressRecord,
  type SaveProgressInput,
  type MasteryStatus,
  type ObjectiveEvidence,
  type ObjectiveMastery,
} from '@/lib/api';
import type { AttemptsByStep, LessonAnswers } from './studentProgress';
import { completedLessonInvalidationKeys, applyProgressToCache } from './progressCache';
import { buildSaveProgressInput } from './progressPersistence';
import { lessonPositionForBlock } from './lessonExperience';
import { coalesceProgressSave, IN_PROGRESS_SAVE_DEBOUNCE_MS, shouldSaveProgressImmediately } from './progressSavePolicy';
import type { LessonDocument } from '@/lib/api/types';

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
  originalBlockIndexOverride?: number,
) => void;

export function useLessonProgressSaver(params: {
  baseElapsedTime: RefObject<number>;
  setObjectiveMastery: Dispatch<SetStateAction<Record<string, ObjectiveMastery>>>;
  setSavedObjectiveEvidence: Dispatch<SetStateAction<Record<string, ObjectiveEvidence[]>>>;
  startTime: RefObject<number>;
  studentId: number | undefined;
  topicId: number;
  lessonVersionId?: number | null;
  lessonDocument?: LessonDocument;
  activeOriginalIndices: number[];
  avatarEnabled: boolean;
  audioEnabled: boolean;
}) {
  const {
    baseElapsedTime,
    setObjectiveMastery,
    setSavedObjectiveEvidence,
    startTime,
    studentId,
    topicId,
    lessonVersionId,
    lessonDocument,
    activeOriginalIndices,
    avatarEnabled,
    audioEnabled,
  } = params;
  const { mutate: mutateProgress, error: saveProgressError } = useSaveProgress();
  const queryClient = useQueryClient();
  const pendingSaveRef = useRef<SaveProgressInput | null>(null);
  const pendingStatusRef = useRef<SaveProgressInput['status']>('in_progress');
  const pendingTimerRef = useRef<number | null>(null);

  const applySavedProgress = useCallback((data: ProgressRecord, status: SaveProgressInput['status']) => {
    applyProgressToCache(queryClient, data);
    if (status === 'completed') {
      setObjectiveMastery(data.objective_mastery || {});
      setSavedObjectiveEvidence(data.objective_evidence || {});
      completedLessonInvalidationKeys().forEach((queryKey) => {
        queryClient.invalidateQueries({ queryKey });
      });
    }
  }, [queryClient, setObjectiveMastery, setSavedObjectiveEvidence]);

  const commitProgress = useCallback((input: SaveProgressInput, status: SaveProgressInput['status']) => {
    mutateProgress(input, {
      onSuccess: (data) => applySavedProgress(data, status),
    });
  }, [applySavedProgress, mutateProgress]);

  const clearPendingTimer = useCallback(() => {
    if (pendingTimerRef.current === null) return;
    window.clearTimeout(pendingTimerRef.current);
    pendingTimerRef.current = null;
  }, []);

  const flushPendingProgress = useCallback(() => {
    const pending = pendingSaveRef.current;
    if (!pending) return;
    const status = pendingStatusRef.current;
    pendingSaveRef.current = null;
    clearPendingTimer();
    commitProgress(pending, status);
  }, [clearPendingTimer, commitProgress]);

  useEffect(() => () => flushPendingProgress(), [flushPendingProgress]);

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
    originalBlockIndexOverride,
  ) => {
    if (!studentId) return;
    const elapsedTimeSec = baseElapsedTime.current + Math.round((Date.now() - startTime.current) / 1000);
    const position = lessonPositionForBlock(
      lessonDocument,
      originalBlockIndexOverride ?? activeOriginalIndices[step],
    );

    const input = buildSaveProgressInput({
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
      lessonVersionId,
      currentEpisodeId: position?.episode.id,
      currentSceneId: position?.scene.id,
      avatarEnabled,
      audioEnabled,
    });
    if (shouldSaveProgressImmediately(status)) {
      pendingSaveRef.current = null;
      clearPendingTimer();
      commitProgress(input, status);
      return;
    }

    pendingSaveRef.current = coalesceProgressSave(pendingSaveRef.current, input);
    pendingStatusRef.current = status;
    clearPendingTimer();
    pendingTimerRef.current = window.setTimeout(flushPendingProgress, IN_PROGRESS_SAVE_DEBOUNCE_MS);
  }, [
    baseElapsedTime,
    clearPendingTimer,
    commitProgress,
    flushPendingProgress,
    startTime,
    studentId,
    topicId,
    lessonVersionId,
    lessonDocument,
    activeOriginalIndices,
    avatarEnabled,
    audioEnabled,
  ]);

  return {
    saveError: saveProgressError as Error | null,
    saveState,
  };
}
