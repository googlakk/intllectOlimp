import { useParams, Link } from 'wouter';
import { ArrowLeft, BookOpen, Loader2, CheckCircle, ChevronDown, RefreshCw, BookMarked, Trophy } from 'lucide-react';
import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { useGetLesson, useSaveProgress, useGetLessonProgress } from '@/lib/api';
import { componentMap, assessmentComponents } from '@/components/blocks/BlockRenderer';
import { useAuth } from '@/components/auth/AuthContext';
import { useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';

export default function Lesson() {
  const params = useParams();
  const subjectId = params.subjectId;
  const topicId = Number(params.topicId);
  const { user } = useAuth();
  
  const { data: lesson, isLoading: isLoadingLesson } = useGetLesson(topicId, 'student');
  const { data: progress, isLoading: isLoadingProgress } = useGetLessonProgress(user?.id || 0, topicId, !!user?.id);
  
  const saveProgressMutation = useSaveProgress();
  const saveError = saveProgressMutation.error as Error | null;
  const queryClient = useQueryClient();
  
  const [currentStep, setCurrentStep] = useState(0);
  const [maxOpenedStep, setMaxOpenedStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string | number, boolean>>({});
  const [attemptsByStep, setAttemptsByStep] = useState<Record<number, number>>({});
  const [retryKeys, setRetryKeys] = useState<Record<number, number>>({});
  const [isCompleted, setIsCompleted] = useState(false);
  const [result, setResult] = useState<{ score: number; level: string } | null>(null);
  
  const initializedForId = useRef<number | null>(null);
  const startTime = useRef(Date.now());
  const baseElapsedTime = useRef(0);
  const lastSaved = useRef<any>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const prefersReducedMotion = useReducedMotion();

  const blocks = lesson?.blocks || [];
  
  const assessmentBlocksCount = useMemo(() => {
    return blocks.filter(b => assessmentComponents.includes(b.component)).length;
  }, [blocks]);

  // Init state from progress
  useEffect(() => {
    if (progress && initializedForId.current !== progress.id && blocks.length > 0) {
      initializedForId.current = progress.id;
      if (progress.status === 'completed') {
        setIsCompleted(true);
        setResult({ score: progress.score || 0, level: progress.mastery_level || 'Начинающий' });
        setCurrentStep(blocks.length);
      } else {
        setCurrentStep(progress.current_step || 0);
      }
      setMaxOpenedStep(progress.max_opened_step || 0);
      setAnswers(progress.answers || {});
      setAttemptsByStep(progress.attempts_by_step || {});
      baseElapsedTime.current = progress.elapsed_time_sec || progress.time_spent_sec || 0;
      startTime.current = Date.now();
      lastSaved.current = {
        current_step: progress.current_step || 0,
        max_opened_step: progress.max_opened_step || 0,
        status: progress.status,
      };
    } else if (progress === null && initializedForId.current !== -1 && blocks.length > 0) {
      initializedForId.current = -1; // brand new
      lastSaved.current = {
        current_step: 0,
        max_opened_step: 0,
        status: 'in_progress',
      };
    }
  }, [progress, blocks.length]);

  const saveState = useCallback((
    step: number, 
    maxStep: number, 
    status: 'in_progress' | 'completed', 
    ans: Record<string | number, boolean>, 
    att: Record<number, number>,
    finalScore?: number,
    finalLevel?: string
  ) => {
    if (!user?.id) return;
    const timeSpentSec = baseElapsedTime.current + Math.round((Date.now() - startTime.current) / 1000);
    
    // update lastSaved
    lastSaved.current = { current_step: step, max_opened_step: maxStep, status };

    saveProgressMutation.mutate({
      student_id: user.id,
      topic_id: topicId,
      status,
      current_step: step,
      max_opened_step: maxStep,
      answers: ans,
      attempts_by_step: att,
      time_spent_sec: timeSpentSec,
      elapsed_time_sec: timeSpentSec,
      ...(status === 'completed' && finalScore !== undefined ? { score: finalScore, mastery_level: finalLevel } : {})
    }, {
      onSuccess: (data) => {
        // Optimistic query patch
        queryClient.setQueryData(['progress', user.id, topicId], data);
        if (status === 'completed') {
           queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] });
           queryClient.invalidateQueries({ queryKey: ['dashboard-students'] });
           queryClient.invalidateQueries({ queryKey: ['subjects'] });
        }
      }
    });
  }, [user?.id, topicId, saveProgressMutation, queryClient]);

  const completeLesson = useCallback((ans: Record<string | number, boolean>, att: Record<number, number>) => {
    let score = 0;
    let level = 'Начинающий';
    
    if (assessmentBlocksCount > 0) {
      const masteryAnswers = Object.entries(ans).filter(([key]) => key.includes('_q'));
      if (masteryAnswers.length > 0) {
        const correctCount = masteryAnswers.filter(([, value]) => value === true).length;
        score = Math.round((correctCount / masteryAnswers.length) * 100);
      } else {
        const correctCount = Object.keys(ans)
          .filter(key => !isNaN(Number(key)))
          .filter(key => ans[key as keyof typeof ans] === true)
          .length;
        score = Math.round((correctCount / assessmentBlocksCount) * 100);
      }
      
      if (score >= 86) level = 'Мастер';
      else if (score >= 66) level = 'Уверенный';
      else if (score >= 41) level = 'Развивающийся';
      else level = 'Начинающий';
    } else {
      score = 100;
      level = 'Мастер';
    }
    
    setResult({ score, level });
    setIsCompleted(true);
    saveState(blocks.length, Math.max(maxOpenedStep, blocks.length - 1), 'completed', ans, att, score, level);
  }, [assessmentBlocksCount, blocks.length, maxOpenedStep, saveState]);

  const handleNextStep = () => {
    if (currentStep === blocks.length - 1) {
      if (!isCompleted) {
        completeLesson(answers, attemptsByStep);
      }
      setCurrentStep(blocks.length);
      return;
    }
    
    const nextStep = currentStep + 1;
    const nextMax = Math.max(maxOpenedStep, nextStep);
    setCurrentStep(nextStep);
    setMaxOpenedStep(nextMax);
    saveState(nextStep, nextMax, 'in_progress', answers, attemptsByStep);
  };

  const handleBlockAnswer = (blockIndex: number, isCorrect: boolean) => {
    const newAnswers = { ...answers, [blockIndex]: isCorrect };
    const newAttempts = { ...attemptsByStep, [blockIndex]: (attemptsByStep[blockIndex] || 0) + 1 };
    
    setAnswers(newAnswers);
    setAttemptsByStep(newAttempts);
    
    // Save immediate state
    saveState(currentStep, maxOpenedStep, 'in_progress', newAnswers, newAttempts);
  };

  const navigateToStep = (index: number) => {
    if (index <= maxOpenedStep) {
      setCurrentStep(index);
      if (!isCompleted) {
        saveState(index, maxOpenedStep, 'in_progress', answers, attemptsByStep);
      }
    }
  };

  const findNearestExplanation = (currentIndex: number) => {
    for (let i = currentIndex - 1; i >= 0; i--) {
      if (!assessmentComponents.includes(blocks[i].component)) {
        return i;
      }
    }
    return 0;
  };

  const isLoading = isLoadingLesson || isLoadingProgress;
  const topicTitle = String(lesson?.lesson_metadata?.topic_name || 'Урок');
  const learningObjective = String(lesson?.lesson_metadata?.learning_objectives || '');
  const phaseLabels: Record<string, string> = {
    ShortExplanation: 'Объяснение',
    KeyConcept: 'Ключевое понятие',
    WorkedExample: 'Разобранный пример',
    GuidedPractice: 'Практика с поддержкой',
    IndependentProblem: 'Самостоятельная практика',
    RetrievalCheck: 'Проверка понимания',
    TextEvidencePicker: 'Работа с текстом',
    ArgumentBuilder: 'Аргументация',
    MasteryCheck: 'Итоговая проверка',
    Reflection: 'Рефлексия',
    MindMap: 'Связи между идеями',
    Timeline: 'Последовательность событий',
    InteractiveGraph: 'Исследование данных',
    Presentation: 'Материал урока',
    Illustration: 'Визуальная модель',
  };

  useEffect(() => {
    if (!isLoading && currentStep < blocks.length) {
      contentRef.current?.focus({ preventScroll: true });
    }
  }, [currentStep, isLoading, blocks.length]);

  return (
    <div className="max-w-5xl mx-auto pb-24">
      <Link href={`/learn/${subjectId}`} className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Назад к программе
      </Link>
      
      <div className="bg-card rounded-[2rem] border border-border shadow-sm overflow-hidden min-h-[500px]">
        <div className="h-48 bg-gradient-to-br from-primary/10 via-primary/5 to-transparent relative p-8 flex flex-col justify-end border-b border-border/50">
          <div className="absolute top-6 right-6 px-4 py-1.5 bg-card/80 backdrop-blur-sm rounded-full shadow-sm text-sm font-bold text-primary flex items-center gap-2 border border-border/50">
            <div className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse"></div>
            Изучение
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-foreground mt-4 mb-2 leading-tight">{topicTitle}</h1>
          {learningObjective && (
            <p className="text-sm md:text-base text-muted-foreground max-w-2xl line-clamp-2">
              Цель: {learningObjective}
            </p>
          )}
        </div>

        <div className="p-6 md:p-10">
          {saveError && (
            <div role="alert" className="mb-6 rounded-xl border border-destructive/20 bg-destructive/10 p-4 text-sm font-medium text-destructive">
              Прогресс пока не сохранён: {saveError.message}
            </div>
          )}
          {isLoading ? (
            <div className="text-center py-20 border-2 border-dashed border-border rounded-3xl bg-muted/10 px-4">
              <Loader2 className="w-16 h-16 text-primary animate-spin mx-auto mb-6" />
              <h3 className="text-2xl font-bold text-foreground mb-3">Загрузка урока</h3>
            </div>
          ) : !lesson || blocks.length === 0 ? (
            <div className="text-center py-20 border-2 border-dashed border-border rounded-3xl bg-muted/10 px-4">
              <BookOpen className="w-16 h-16 text-muted-foreground/30 mx-auto mb-6" />
              <h3 className="text-2xl font-bold text-foreground mb-3">Урок готовится</h3>
              <p className="text-muted-foreground max-w-md mx-auto font-medium">
                Преподаватель еще не опубликовал этот урок. Возвращайтесь позже!
              </p>
            </div>
          ) : isCompleted && result && currentStep === blocks.length ? (
            <div className="text-center py-20 border-2 border-dashed border-primary/30 rounded-3xl bg-primary/5 px-4 animate-in fade-in zoom-in duration-500">
              <CheckCircle className="w-20 h-20 text-primary mx-auto mb-6" />
              <h3 className="text-3xl font-extrabold text-foreground mb-4">Урок завершён!</h3>
              {assessmentBlocksCount > 0 && (
                <div className="flex flex-col items-center justify-center gap-4 mb-8">
                  <div className="text-5xl font-black text-primary">{result.score}%</div>
                  <div className="px-6 py-2 bg-card border border-border rounded-full text-lg font-bold text-foreground shadow-sm">
                    Уровень: <span className="text-primary">{result.level}</span>
                  </div>
                </div>
              )}
              {!assessmentBlocksCount && (
                 <p className="text-muted-foreground font-medium mb-8">Вы успешно изучили материал урока.</p>
              )}
              <div className="flex gap-4 justify-center">
                <button 
                  onClick={() => setCurrentStep(blocks.length - 1)}
                  className="px-6 py-3 border border-border bg-card text-foreground font-bold rounded-xl shadow-sm hover:bg-muted transition-all"
                >
                  Просмотреть ответы
                </button>
                <Link href={`/learn/${subjectId}`}>
                  <button className="px-8 py-3 bg-primary text-primary-foreground font-bold rounded-xl shadow-lg shadow-primary/30 hover:bg-primary/90 hover:-translate-y-0.5 transition-all">
                    Вернуться к курсу
                  </button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="flex flex-col lg:flex-row gap-8 relative">
              {/* Sidebar stepper */}
              <div className="w-full lg:w-64 shrink-0" aria-label="Прогресс урока">
                <div className="sticky top-8 flex flex-col gap-3">
                  <h3 className="text-sm font-bold text-muted-foreground uppercase tracking-wider mb-2">Шаги урока</h3>
                  {blocks.slice(0, maxOpenedStep + 1).map((block, index) => {
                    const isActive = index === currentStep;
                    const isCompletedBlock = index < maxOpenedStep || answers[index] !== undefined;
                    const isAssessment = assessmentComponents.includes(block.component);
                    
                    return (
                      <button
                        key={index}
                        onClick={() => navigateToStep(index)}
                        className={`text-left p-3 rounded-xl border transition-all duration-300 flex items-start gap-3 ${
                          isActive 
                            ? 'bg-primary/5 border-primary shadow-sm ring-1 ring-primary/20' 
                            : 'bg-card border-border hover:border-primary/50'
                        }`}
                      >
                        <div className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                          isCompletedBlock ? 'bg-primary text-primary-foreground' : (isActive ? 'bg-primary/20 text-primary' : 'bg-muted text-muted-foreground')
                        }`}>
                          {isCompletedBlock ? <CheckCircle className="w-3.5 h-3.5" /> : index + 1}
                        </div>
                        <div className="flex-1 overflow-hidden">
                          <div className={`text-sm font-semibold truncate ${isActive ? 'text-foreground' : 'text-muted-foreground'}`}>
                            {isAssessment ? 'Практика' : 'Теория'}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                  {isCompleted && (
                    <button
                      onClick={() => setCurrentStep(blocks.length)}
                      className={`text-left p-3 rounded-xl border transition-all duration-300 flex items-start gap-3 mt-4 ${
                        currentStep === blocks.length 
                          ? 'bg-primary/5 border-primary shadow-sm ring-1 ring-primary/20' 
                          : 'bg-card border-border hover:border-primary/50'
                      }`}
                    >
                      <div className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                        currentStep === blocks.length ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
                      }`}>
                        <Trophy className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex-1 overflow-hidden">
                        <div className={`text-sm font-semibold truncate ${currentStep === blocks.length ? 'text-foreground' : 'text-muted-foreground'}`}>
                          Итоги
                        </div>
                      </div>
                    </button>
                  )}
                </div>
              </div>

              {/* Main content area */}
              <div ref={contentRef} tabIndex={-1} className="flex-1 outline-none" aria-live="polite">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-primary">
                      {phaseLabels[blocks[currentStep]?.component] || 'Учебный шаг'}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      Шаг {currentStep + 1} из {blocks.length}
                    </p>
                  </div>
                  <div
                    className="w-full sm:w-48 h-2 rounded-full bg-muted overflow-hidden"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={blocks.length}
                    aria-valuenow={currentStep + 1}
                  >
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${((currentStep + 1) / blocks.length) * 100}%` }}
                    />
                  </div>
                </div>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={currentStep}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    transition={{ duration: prefersReducedMotion ? 0 : 0.3 }}
                    className="space-y-8"
                  >
                    {(() => {
                      const block = blocks[currentStep];
                      const Component = componentMap[block.component];
                      if (!Component) return <div className="text-destructive">Неизвестный блок</div>;

                      const isAssessment = assessmentComponents.includes(block.component);
                      const isAnswered = answers[currentStep] !== undefined;
                      const isCorrect = answers[currentStep] === true;
                      
                      const injectProps = isAssessment 
                        ? { onAnswer: (correct: boolean, detail?: { questionIndex: number; isFinished: boolean }) => {
                              if (block.component === 'MasteryCheck' && detail) {
                                const intermediateAns = { ...answers, [`${currentStep}_q${detail.questionIndex}`]: correct };
                                setAnswers(intermediateAns);
                                
                                if (!detail.isFinished) {
                                  saveState(currentStep, maxOpenedStep, 'in_progress', intermediateAns, attemptsByStep);
                                  return;
                                }
                                
                                // Block finished, compute overall block success
                                handleBlockAnswer(currentStep, correct);
                                return;
                              }
                              
                              handleBlockAnswer(currentStep, correct);
                            } 
                          } 
                        : {};

                      return (
                        <div key={`block-${currentStep}-${retryKeys[currentStep] || 0}`} className="bg-card rounded-2xl border border-border/50 shadow-sm p-6 lg:p-8">
                          <Component {...block.content} {...injectProps} />

                          {/* Navigation Controls */}
                          <div className="mt-8 pt-6 border-t border-border flex flex-wrap gap-4 items-center justify-between">
                            
                            {/* Assessment Feedback and Retry */}
                            {isAssessment && isAnswered && !isCorrect && (
                              <div className="w-full p-4 rounded-xl bg-destructive/5 border border-destructive/20 mb-4 flex flex-col sm:flex-row gap-4 justify-between items-center">
                                <div className="text-sm font-medium text-destructive">
                                  Материал требует повторения.
                                </div>
                                <div className="flex gap-3">
                                  <button
                                    onClick={() => navigateToStep(findNearestExplanation(currentStep))}
                                    className="inline-flex items-center gap-2 px-4 py-2 bg-background border border-border rounded-lg text-sm font-semibold shadow-sm hover:bg-muted transition-colors"
                                  >
                                    <BookMarked className="w-4 h-4" /> Повторить теорию
                                  </button>
                                  <button
                                    onClick={() => {
                                      const newAns = Object.fromEntries(
                                        Object.entries(answers).filter(([key]) => (
                                          key !== String(currentStep) && !key.startsWith(`${currentStep}_q`)
                                        ))
                                      );
                                      setAnswers(newAns);
                                      setRetryKeys(prev => ({ ...prev, [currentStep]: (prev[currentStep] || 0) + 1 }));
                                      saveState(currentStep, maxOpenedStep, 'in_progress', newAns, attemptsByStep);
                                    }}
                                    className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-semibold shadow-sm hover:bg-primary/90 transition-colors"
                                  >
                                    <RefreshCw className="w-4 h-4" /> Попробовать снова
                                  </button>
                                </div>
                              </div>
                            )}

                            {/* Continue Button */}
                            {(!isAssessment || isAnswered) && (
                              <div className="w-full flex justify-end">
                                <button
                                  onClick={() => {
                                    if (currentStep === blocks.length - 1 && isCompleted) {
                                      setCurrentStep(blocks.length); // go to summary
                                    } else {
                                      handleNextStep();
                                    }
                                  }}
                                  className="px-8 py-3.5 bg-primary text-primary-foreground font-bold rounded-xl shadow-sm hover:bg-primary/90 hover:-translate-y-0.5 transition-all flex items-center gap-2"
                                >
                                  {currentStep === blocks.length - 1 ? 'Завершить урок' : 'Продолжить'}
                                  <ChevronDown className="w-5 h-5 -rotate-90" />
                                </button>
                              </div>
                            )}

                          </div>
                        </div>
                      );
                    })()}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
