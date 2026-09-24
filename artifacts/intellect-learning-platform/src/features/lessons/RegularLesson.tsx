import { LearningContext } from './LearningContext';
import { useParams } from 'wouter';
import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useRestartLessonProgress, type ObjectiveEvidence, type ObjectiveMastery } from '@/lib/api';
import { useAuth } from '@/components/auth/AuthContext';
import { useReducedMotion } from 'framer-motion';
import {
  buildActiveLessonRoute,
  calculateDiagnosticCompletion,
  calculateLessonCompletion,
  isAssessmentBlock,
  shouldReopenCompletedProgress,
  type AttemptsByStep,
  type LessonAnswers,
} from '@/features/lessons/studentProgress';
import { restoreLessonProgress } from '@/features/lessons/progressRestore';
import { advanceLessonStep, applyBlockAnswer, canNavigateToStep } from '@/features/lessons/lessonNavigation';
import { useLessonProgressSaver } from '@/features/lessons/progressSaver';
import { useStudentLessonData } from '@/features/lessons/lessonManifest';
import { lessonHeaderText, lessonObjectives } from '@/features/lessons/lessonMetadata';
import { StudentLessonPageView } from '@/features/lessons/studentLessonPageView';
import { useNextLessonManifestPrefetch } from '@/features/lessons/lessonPrefetch';
export function RegularLesson() {
  const { subjectId, topicId: topicIdParam } = useParams();
  const topicId = Number(topicIdParam);
  const { user } = useAuth();
  const { lesson, progress, isLoading, error, refetch } = useStudentLessonData(topicId, user?.id);
  useNextLessonManifestPrefetch({ studentId: user?.id, subjectId: Number(subjectId), topicId });
  const [currentStep, setCurrentStep] = useState(0);
  const [maxOpenedStep, setMaxOpenedStep] = useState(0);
  const [answers, setAnswers] = useState<LessonAnswers>({});
  const [attemptsByStep, setAttemptsByStep] = useState<AttemptsByStep>({});
  const [retryKeys, setRetryKeys] = useState<Record<number, number>>({});
  const [isCompleted, setIsCompleted] = useState(false);
  const [result, setResult] = useState<{ score: number; level: string } | null>(null);
  const [objectiveMastery, setObjectiveMastery] = useState<Record<string, ObjectiveMastery>>({});
  const [savedObjectiveEvidence, setSavedObjectiveEvidence] = useState<Record<string, ObjectiveEvidence[]>>({});
  const [diagnosticComplete, setDiagnosticComplete] = useState(false);
  const [avatarEnabled, setAvatarEnabled] = useState(true);
  const [audioEnabled, setAudioEnabled] = useState(true);
  const restartProgress = useRestartLessonProgress();
  const initializedForId = useRef<number | null>(null);
  const startTime = useRef(Date.now());
  const baseElapsedTime = useRef(0);
  const restoredCompletionPositioned = useRef(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = useReducedMotion();
  const blocks = lesson?.blocks || []; const objectives = useMemo(() => lessonObjectives(lesson), [lesson]);
  const { activeBlocks, activeOriginalIndices, diagnosticOriginalIndices, hasObjectiveRoute } = useMemo(
    () => buildActiveLessonRoute(blocks, objectives, diagnosticComplete, objectiveMastery),
    [blocks, diagnosticComplete, objectiveMastery, objectives],
  );
  const { saveError, saveState } = useLessonProgressSaver({
    baseElapsedTime,
    setObjectiveMastery,
    setSavedObjectiveEvidence,
    startTime,
    studentId: user?.id,
    topicId,
    lessonVersionId: lesson?.active_version_id,
    lessonDocument: lesson?.lesson_document,
    activeOriginalIndices,
    avatarEnabled,
    audioEnabled,
  });
  useEffect(() => {
    if (progress && initializedForId.current !== progress.id && blocks.length > 0) {
      initializedForId.current = progress.id;
      const restored = restoreLessonProgress(progress, diagnosticOriginalIndices);
      setObjectiveMastery(restored.objectiveMastery);
      setSavedObjectiveEvidence(restored.objectiveEvidence);
      setIsCompleted(restored.isCompleted);
      setResult(restored.result);
      restoredCompletionPositioned.current = false;
      if (!restored.isCompleted) setCurrentStep(restored.currentStep);
      setMaxOpenedStep(restored.maxOpenedStep);
      setAnswers(restored.answers);
      setAttemptsByStep(restored.attemptsByStep);
      setDiagnosticComplete(restored.diagnosticComplete);
      setAvatarEnabled(progress.avatar_enabled ?? true);
      setAudioEnabled(progress.audio_enabled ?? true);
      baseElapsedTime.current = restored.baseElapsedTimeSec;
      startTime.current = Date.now();
    } else if (progress === null && initializedForId.current !== -1 && blocks.length > 0) {
      initializedForId.current = -1;
    }
  }, [progress, blocks.length, objectives.length, diagnosticOriginalIndices.length]);
  useEffect(() => {
    if (isCompleted && !restoredCompletionPositioned.current && activeBlocks.length > 0) {
      setCurrentStep(activeBlocks.length);
      restoredCompletionPositioned.current = true;
    }
  }, [activeBlocks.length, isCompleted]);
  useEffect(() => {
    if (!shouldReopenCompletedProgress({ activeBlocksLength: activeBlocks.length, isCompleted, maxOpenedStep })) return;
    const resumeStep = Math.max(0, Math.min(maxOpenedStep, activeBlocks.length - 1));
    restoredCompletionPositioned.current = true;
    setIsCompleted(false);
    setResult(null);
    setCurrentStep(resumeStep);
    saveState(resumeStep, maxOpenedStep, 'in_progress', answers, attemptsByStep);
  }, [activeBlocks.length, answers, attemptsByStep, isCompleted, maxOpenedStep, saveState]);
  const completeLesson = useCallback((ans: LessonAnswers, att: AttemptsByStep) => {
    const { score, level, mastery, evidence, masteryStatus } = calculateLessonCompletion({
      activeBlocks,
      activeOriginalIndices,
      objectives,
      answers: ans,
      attemptsByStep: att,
      currentMastery: objectiveMastery,
      savedObjectiveEvidence,
    });
    setObjectiveMastery(mastery);
    setSavedObjectiveEvidence(evidence);
    setResult({ score, level });
    setIsCompleted(true);
    saveState(activeBlocks.length, Math.max(maxOpenedStep, activeBlocks.length - 1), 'completed', ans, att, score, level, mastery, evidence, masteryStatus);
  }, [activeBlocks, activeOriginalIndices, objectives, objectiveMastery, maxOpenedStep, saveState, savedObjectiveEvidence]);
  const completeDiagnostic = useCallback(() => {
    const { mastery, evidence } = calculateDiagnosticCompletion({
      blocks,
      diagnosticOriginalIndices,
      objectives,
      answers,
      attemptsByStep,
    });
    setObjectiveMastery(mastery);
    setDiagnosticComplete(true);
    setCurrentStep(0);
    setMaxOpenedStep(0);
    const nextIndex = buildActiveLessonRoute(blocks, objectives, true, mastery).activeOriginalIndices[0];
    saveState(0, 0, 'in_progress', answers, attemptsByStep, undefined, undefined, mastery, evidence, 'in_progress', nextIndex);
  }, [answers, attemptsByStep, blocks, diagnosticOriginalIndices, objectives, saveState]);
  const handleNextStep = () => {
    if (currentStep === activeBlocks.length - 1) {
      if (hasObjectiveRoute && !diagnosticComplete) {
        completeDiagnostic();
        return;
      }
      if (!isCompleted) completeLesson(answers, attemptsByStep);
      setCurrentStep(activeBlocks.length);
      return;
    }
    const { nextStep, nextMaxOpenedStep } = advanceLessonStep(currentStep, maxOpenedStep);
    setCurrentStep(nextStep);
    setMaxOpenedStep(nextMaxOpenedStep);
    saveState(nextStep, nextMaxOpenedStep, 'in_progress', answers, attemptsByStep);
  };
  const handleBlockAnswer = (blockIndex: number, isCorrect: boolean) => {
    const { answers: newAnswers, attemptsByStep: newAttempts } = applyBlockAnswer({
      activeOriginalIndices,
      answers,
      attemptsByStep,
      blockIndex,
      isCorrect,
    });
    setAnswers(newAnswers);
    setAttemptsByStep(newAttempts);
    saveState(currentStep, maxOpenedStep, 'in_progress', newAnswers, newAttempts);
  };
  const navigateToStep = (index: number) => {
    if (!canNavigateToStep(index, maxOpenedStep)) return;
    setCurrentStep(index);
    if (!isCompleted) saveState(index, maxOpenedStep, 'in_progress', answers, attemptsByStep);
  };
  const restartLesson = async () => {
    if (!user?.id) return;
    initializedForId.current = null;
    restoredCompletionPositioned.current = false;
    await restartProgress.mutateAsync({ studentId: user.id, topicId });
    await refetch();
  };
  const { learningObjective, topicTitle } = lessonHeaderText(lesson);
  useEffect(() => {
    if (!isLoading && currentStep < activeBlocks.length) contentRef.current?.focus({ preventScroll: true });
  }, [currentStep, isLoading, activeBlocks.length]);
  return (
    <StudentLessonPageView
      learningContext={lesson && user ? <LearningContext lesson={lesson} studentId={user.id} subjectId={subjectId ?? ''} /> : null}
      activeBlocks={activeBlocks}
      activeOriginalIndices={activeOriginalIndices}
      answers={answers}
      assessmentBlocksCount={activeBlocks.filter(isAssessmentBlock).length}
      attemptsByStep={attemptsByStep}
      contentRef={contentRef}
      currentStep={currentStep}
      isCompleted={isCompleted}
      isDiagnosticRoute={hasObjectiveRoute && !diagnosticComplete}
      isEmpty={!lesson || blocks.length === 0}
      isLoading={isLoading}
      loadError={error}
      learningObjective={learningObjective}
      lessonDocument={lesson?.lesson_document} lessonVersionId={lesson?.active_version_id}
      maxOpenedStep={maxOpenedStep}
      objectiveMastery={objectiveMastery}
      objectives={objectives}
      prefersReducedMotion={prefersReducedMotion}
      result={result}
      retryKeys={retryKeys}
      saveError={saveError}
      subjectId={subjectId}
      topicTitle={topicTitle}
      warpGates={progress?.warp_gates}
      onAnswer={handleBlockAnswer}
      onNavigate={navigateToStep}
      onNext={handleNextStep}
      onOpenSummary={() => setCurrentStep(activeBlocks.length)}
      onReviewAnswers={() => setCurrentStep(activeBlocks.length - 1)}
      onRestart={restartLesson}
      isRestarting={restartProgress.isPending}
      restartError={restartProgress.error as Error | null}
      onSaveIntermediate={(nextAnswers, nextAttempts) => saveState(currentStep, maxOpenedStep, 'in_progress', nextAnswers, nextAttempts)}
      onSetAnswers={setAnswers}
      onSetRetryKeys={setRetryKeys}
      avatarEnabled={avatarEnabled}
      audioEnabled={audioEnabled}
      onAvatarEnabledChange={setAvatarEnabled}
      onAudioEnabledChange={setAudioEnabled}
    />
  );
}
