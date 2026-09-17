import { useParams, Link } from 'wouter';
import { ArrowLeft, BookOpen, Loader2, CheckCircle } from 'lucide-react';
import { useState, useRef, useEffect, useMemo } from 'react';
import { useGetLesson, useSaveProgress } from '@/lib/api';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import { useAuth } from '@/components/auth/AuthContext';
import { useQueryClient } from '@tanstack/react-query';

const assessmentComponents = [
  'GuidedPractice',
  'IndependentProblem',
  'RetrievalCheck',
  'TextEvidencePicker',
  'ArgumentBuilder',
  'MasteryCheck'
];

export default function Lesson() {
  const params = useParams();
  const subjectId = params.subjectId;
  const topicId = Number(params.topicId);
  const { user } = useAuth();
  
  const { data: lesson, isLoading } = useGetLesson(topicId, 'student');
  const saveProgressMutation = useSaveProgress();
  const queryClient = useQueryClient();
  
  const [answers, setAnswers] = useState<Record<number, boolean>>({});
  const [isCompleted, setIsCompleted] = useState(false);
  const [result, setResult] = useState<{ score: number; level: string } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [startTime] = useState(Date.now());
  const savedRef = useRef(false);

  const blocks = lesson?.blocks || [];
  
  const assessmentBlocksCount = useMemo(() => {
    return blocks.filter(b => assessmentComponents.includes(b.component)).length;
  }, [blocks]);

  const handleAnswer = (blockIndex: number, isCorrect: boolean) => {
    setAnswers(prev => ({ ...prev, [blockIndex]: isCorrect }));
  };

  useEffect(() => {
    if (assessmentBlocksCount > 0 && Object.keys(answers).length === assessmentBlocksCount && !savedRef.current) {
      completeLesson();
    }
  }, [answers, assessmentBlocksCount]);

  const persistResult = (score: number, level: string) => {
    if (!user?.id || savedRef.current) return;
    savedRef.current = true;
    setSaveError(null);
    const timeSpentSec = Math.round((Date.now() - startTime) / 1000);
    saveProgressMutation.mutate({
      topic_id: topicId,
      student_id: user.id,
      score,
      mastery_level: level,
      time_spent_sec: timeSpentSec,
    }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['dashboard-overview'] });
        queryClient.invalidateQueries({ queryKey: ['dashboard-students'] });
        queryClient.invalidateQueries({ queryKey: ['subjects'] });
      },
      onError: (saveError) => {
        savedRef.current = false;
        setSaveError(saveError.message || 'Не удалось сохранить результат');
      },
    });
  };

  const completeLesson = () => {
    if (savedRef.current) return;
    let score = 0;
    let level = 'Начинающий';
    
    if (assessmentBlocksCount > 0) {
      const correctCount = Object.values(answers).filter(Boolean).length;
      score = Math.round((correctCount / assessmentBlocksCount) * 100);
      
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
    persistResult(score, level);
  };

  return (
    <div className="max-w-5xl mx-auto pb-24">
      <Link href={`/learn/${subjectId}`} className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Назад к программе
      </Link>
      
      <div className="bg-card rounded-[2rem] border border-border shadow-sm overflow-hidden">
        <div className="h-48 bg-gradient-to-br from-primary/10 via-primary/5 to-transparent relative p-8 flex flex-col justify-end border-b border-border/50">
          <div className="absolute top-6 right-6 px-4 py-1.5 bg-card/80 backdrop-blur-sm rounded-full shadow-sm text-sm font-bold text-primary flex items-center gap-2 border border-border/50">
            <div className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse"></div>
            Изучение
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-foreground mt-4 mb-2 leading-tight">Урок</h1>
        </div>

        <div className="p-6 md:p-10 space-y-12">
          {isLoading ? (
            <div className="text-center py-20 border-2 border-dashed border-border rounded-3xl bg-muted/10 px-4">
              <Loader2 className="w-16 h-16 text-primary animate-spin mx-auto mb-6" />
              <h3 className="text-2xl font-bold text-foreground mb-3">Загрузка урока</h3>
              <p className="text-muted-foreground max-w-md mx-auto font-medium">
                Пожалуйста, подождите...
              </p>
            </div>
          ) : !lesson ? (
            <div className="text-center py-20 border-2 border-dashed border-border rounded-3xl bg-muted/10 px-4">
              <BookOpen className="w-16 h-16 text-muted-foreground/30 mx-auto mb-6" />
              <h3 className="text-2xl font-bold text-foreground mb-3">Урок готовится</h3>
              <p className="text-muted-foreground max-w-md mx-auto font-medium">
                Преподаватель еще не опубликовал этот урок. Возвращайтесь позже!
              </p>
            </div>
          ) : isCompleted && result ? (
            <div className="text-center py-20 border-2 border-dashed border-primary/30 rounded-3xl bg-primary/5 px-4">
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
              {saveError && (
                <div className="mb-6">
                  <p className="text-sm font-semibold text-destructive mb-3">{saveError}</p>
                  <button
                    onClick={() => persistResult(result.score, result.level)}
                    disabled={saveProgressMutation.isPending}
                    className="px-5 py-2.5 border border-border bg-card font-bold rounded-xl hover:bg-muted transition-colors disabled:opacity-50"
                  >
                    {saveProgressMutation.isPending ? 'Сохранение...' : 'Повторить сохранение'}
                  </button>
                </div>
              )}
              <Link href={`/learn/${subjectId}`}>
                <button className="px-8 py-3.5 bg-primary text-primary-foreground font-bold rounded-xl shadow-lg shadow-primary/30 hover:bg-primary/90 hover:-translate-y-0.5 transition-all">
                  Вернуться к курсу
                </button>
              </Link>
            </div>
          ) : (
            <div className="space-y-12">
              <BlockRenderer blocks={blocks} onAnswer={handleAnswer} />
              
              {assessmentBlocksCount === 0 && (
                <div className="pt-8 border-t border-border flex justify-center">
                  <button 
                    onClick={completeLesson}
                    disabled={savedRef.current || saveProgressMutation.isPending}
                    className="px-8 py-3.5 bg-primary text-primary-foreground font-bold rounded-xl shadow-lg shadow-primary/30 hover:bg-primary/90 hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:hover:translate-y-0"
                  >
                    {saveProgressMutation.isPending ? 'Сохранение...' : 'Завершить урок'}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
