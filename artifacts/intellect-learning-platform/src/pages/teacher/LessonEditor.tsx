import { useParams, Link } from 'wouter';
import { AlertTriangle, ArrowLeft, Loader2, Sparkles, Globe, EyeOff, CheckCircle2, XCircle } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useGetLesson, useGenerateLesson, usePublishLesson, useUnpublishLesson } from '@/lib/api';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import { useAuth } from '@/components/auth/AuthContext';
import { useQueryClient } from '@tanstack/react-query';

export default function LessonEditor() {
  const { topicId } = useParams();
  const tId = Number(topicId);
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const { data: lesson, isLoading: isLoadingLesson } = useGetLesson(tId, 'teacher');
  const generateLessonMutation = useGenerateLesson();
  const publishLessonMutation = usePublishLesson();
  const unpublishLessonMutation = useUnpublishLesson();
  const [warningsAcknowledged, setWarningsAcknowledged] = useState(false);

  const blocks = lesson?.blocks || [];
  const isPublished = lesson?.status === 'published';
  const metadata = lesson?.lesson_metadata;
  const objectives = metadata?.objectives || [];
  const qualityReport = metadata?.quality_report;
  const hasObjectiveContract = objectives.length > 0 || Boolean(qualityReport);
  const objectiveIdsForBlock = (block: typeof blocks[number]) => {
    const ids = block.content?.objective_ids;
    if (Array.isArray(ids)) return ids.filter((id): id is string => typeof id === 'string');
    return typeof ids === 'string' ? [ids] : [];
  };
  const qualityMessage = (item: unknown) => {
    if (typeof item === 'string') return item;
    if (item && typeof item === 'object') {
      const value = item as Record<string, unknown>;
      return String(value.message || value.detail || value.code || JSON.stringify(item));
    }
    return String(item);
  };
  const groupedMessages = (items: unknown[]) => {
    const groups = new Map<string, { message: string; count: number }>();
    items.forEach((item) => {
      const message = qualityMessage(item);
      const code = item && typeof item === 'object'
        ? String((item as Record<string, unknown>).code || message)
        : message;
      const current = groups.get(code);
      groups.set(code, { message, count: (current?.count || 0) + 1 });
    });
    return Array.from(groups.values()).map(({ message, count }) => (
      count > 1 ? `${message} (${count} блоков)` : message
    ));
  };
  const coverage = useMemo(() => objectives.map((objective) => {
    const related = blocks.filter((block) => objectiveIdsForBlock(block).includes(objective.id));
    const report = qualityReport?.objectives?.[objective.id];
    return {
      objective,
      explanation: report ? (report.explanation?.length || 0) > 0 : related.some((block) => ['ShortExplanation', 'KeyConcept', 'WorkedExample', 'Presentation', 'Illustration'].includes(block.component)),
      practice: report ? (report.practice?.length || 0) > 0 : related.some((block) => ['GuidedPractice', 'IndependentProblem', 'RetrievalCheck', 'TextEvidencePicker', 'ArgumentBuilder'].includes(block.component)),
      assessment: report ? (report.assessment?.length || 0) > 0 : related.some((block) => block.component === 'MasteryCheck' || ['IndependentProblem', 'RetrievalCheck', 'TextEvidencePicker', 'ArgumentBuilder'].includes(block.component)),
    };
  }), [objectives, blocks, qualityReport]);
  const blockingIssues = [
    ...(qualityReport?.publishable === false ? ['Автоматическая проверка считает урок непригодным к публикации'] : []),
    ...groupedMessages(qualityReport?.errors || []),
    ...(qualityReport?.gaps || []).map((gap) => typeof gap === 'string' ? `Не покрыта цель: ${gap}` : `Не покрыта цель: ${gap.objective || gap.objective_id || 'неизвестная цель'} (${(gap.missing || []).join(', ')})`),
    ...(!hasObjectiveContract && blocks.length > 0 ? ['Старый урок нужно проверить или перегенерировать перед публикацией'] : []),
    ...(hasObjectiveContract && !qualityReport ? ['Для нового урока отсутствует отчёт проверки качества'] : []),
  ];
  const warningMessages = groupedMessages(qualityReport?.warnings || []);
  const canPublish = blockingIssues.length === 0 && (warningMessages.length === 0 || warningsAcknowledged);

  const handleGenerate = () => {
    if (!user) return;
    generateLessonMutation.mutate({ topic_id: tId, teacher_id: user.id }, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['lesson', tId, 'teacher'] });
        queryClient.invalidateQueries({ queryKey: ['lesson-status', tId] });
      }
    });
  };

  const handleTogglePublish = () => {
    if (!lesson || !user) return;
    if (isPublished) {
      unpublishLessonMutation.mutate(lesson.id, {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['lesson', tId, 'teacher'] });
          queryClient.invalidateQueries({ queryKey: ['lesson-status', tId] });
        }
      });
    } else {
      publishLessonMutation.mutate({
        lesson_id: lesson.id,
        teacher_id: user.id,
        acknowledge_warnings: warningsAcknowledged,
      }, {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ['lesson', tId, 'teacher'] });
          queryClient.invalidateQueries({ queryKey: ['lesson-status', tId] });
        }
      });
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)] flex flex-col pb-12">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 shrink-0">
        <div>
          <Link href="/dashboard/lessons" className="inline-flex items-center gap-2 text-sm font-bold text-muted-foreground hover:text-foreground mb-3 transition-colors">
            <ArrowLeft className="w-4 h-4" /> Назад к темам
          </Link>
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
              Редактор урока <span className="text-sm font-mono font-bold bg-muted text-muted-foreground px-2.5 py-1 rounded-lg">ID: {topicId}</span>
            </h1>
            {!isLoadingLesson && lesson && (
              <span className={`px-3 py-1 rounded-full text-xs font-bold border ${isPublished ? 'bg-green-500/10 text-green-600 border-green-500/20' : 'bg-yellow-500/10 text-yellow-600 border-yellow-500/20'}`}>
                {isPublished ? 'Опубликован' : 'Черновик'}
              </span>
            )}
          </div>
        </div>
        <div className="flex gap-3">
          {blocks.length > 0 && (
            <button 
              onClick={handleTogglePublish}
              disabled={publishLessonMutation.isPending || unpublishLessonMutation.isPending || (!isPublished && !canPublish)}
              className={`px-6 py-2.5 text-sm font-bold rounded-xl border shadow-sm transition-colors flex items-center gap-2 ${
                isPublished 
                  ? 'bg-card text-foreground border-border hover:bg-muted' 
                  : 'bg-primary text-primary-foreground border-transparent hover:bg-primary/90'
              }`}
            >
              {isPublished ? <><EyeOff className="w-4 h-4" /> Снять с публикации</> : <><Globe className="w-4 h-4" /> Опубликовать</>}
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 min-h-0 bg-card rounded-[2rem] border border-border shadow-sm p-6 md:p-10 overflow-y-auto custom-scrollbar">
        {(publishLessonMutation.error || generateLessonMutation.error) && (
          <div data-testid="status-api-error" role="alert" className="mb-6 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm font-medium text-destructive">
            {((publishLessonMutation.error || generateLessonMutation.error) as Error).message}
          </div>
        )}
        {isLoadingLesson ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin mb-4 text-primary" />
            <p className="font-medium">Загрузка урока...</p>
          </div>
        ) : blocks.length > 0 ? (
          <div>
            {!hasObjectiveContract && (
              <div data-testid="status-legacy-review" role="alert" className="mb-6 flex gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-foreground">
                <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
                <div>
                  <p className="font-bold">Старый урок требует повторной проверки</p>
                  <p className="mt-1 text-muted-foreground">В этом уроке нет разметки целей КТП. Проверьте материалы вручную или перегенерируйте урок перед публикацией.</p>
                </div>
              </div>
            )}
            {blockingIssues.length > 0 && (
              <div data-testid="status-quality-blocked" role="alert" className="mb-6 rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-foreground">
                <div className="flex items-start gap-3">
                  <XCircle className="h-5 w-5 shrink-0 text-destructive" />
                  <div>
                    <p className="font-bold text-destructive">Публикация заблокирована до проверки урока</p>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
                      {blockingIssues.map((issue, index) => <li key={`${issue}-${index}`}>{issue}</li>)}
                    </ul>
                  </div>
                </div>
              </div>
            )}
            {blockingIssues.length === 0 && warningMessages.length > 0 && (
              <div data-testid="status-quality-warnings" className="mb-6 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-foreground">
                <p className="font-bold">Нужна проверка учителя</p>
                <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
                  {warningMessages.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}
                </ul>
                <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-lg border border-amber-500/20 bg-card/60 p-3">
                  <input
                    type="checkbox"
                    checked={warningsAcknowledged}
                    onChange={(event) => setWarningsAcknowledged(event.target.checked)}
                    className="mt-0.5 h-4 w-4"
                  />
                  <span>Я проверил предупреждения и подтверждаю публикацию урока.</span>
                </label>
              </div>
            )}
            {objectives.length > 0 && (
              <section data-testid="objective-coverage-matrix" className="mb-8 rounded-2xl border border-border bg-muted/20 p-5">
                <div className="mb-4">
                  <h2 className="text-lg font-bold text-foreground">Покрытие целей КТП</h2>
                  <p className="mt-1 text-sm text-muted-foreground">Каждая цель должна иметь объяснение, практику и проверяемое доказательство.</p>
                </div>
                <div className="space-y-3">
                  {coverage.map(({ objective, explanation, practice, assessment }) => (
                    <div data-testid={`objective-row-${objective.id}`} key={objective.id} className="rounded-xl border border-border bg-card p-4">
                      <p className="mb-3 font-semibold text-foreground">{objective.text}</p>
                      <div className="grid grid-cols-3 gap-2 text-xs font-semibold">
                        {[
                          ['Объяснение', explanation],
                          ['Практика', practice],
                          ['Проверка', assessment],
                        ].map(([label, present]) => (
                          <div key={String(label)} className={`flex items-center gap-1.5 rounded-lg px-3 py-2 ${present ? 'bg-green-500/10 text-green-700 dark:text-green-400' : 'bg-destructive/10 text-destructive'}`}>
                            {present ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                            {label}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}
            {lesson?.lesson_metadata?.teacher_review_required === true && (
              <div role="alert" className="mb-6 flex gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-foreground">
                <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600" />
                <div>
                  <p className="font-bold">Предметный профиль требует проверки</p>
                  <p className="mt-1 text-muted-foreground">
                    Система использовала общий сценарий. Проверьте порядок этапов и задания перед публикацией.
                  </p>
                </div>
              </div>
            )}
            <div className="flex justify-end mb-6">
               <button 
                  onClick={handleGenerate}
                  disabled={generateLessonMutation.isPending}
                  className="px-4 py-2 bg-muted/50 text-foreground font-bold rounded-xl hover:bg-muted transition-colors flex items-center gap-2 text-sm"
               >
                 {generateLessonMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin text-primary" /> : <Sparkles className="w-4 h-4 text-primary" />}
                 Перегенерировать AI
               </button>
            </div>
            <BlockRenderer blocks={blocks} />
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-center">
             <div className="w-20 h-20 bg-primary/10 border border-primary/20 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-sm">
               <Sparkles className="w-10 h-10 text-primary" />
             </div>
             <h3 className="text-2xl font-bold text-foreground mb-3">Урок пока пуст</h3>
             <p className="text-muted-foreground text-sm mb-8 font-medium max-w-sm">
               Сгенерируйте материалы урока с помощью ИИ. Это займет около 15-30 секунд.
             </p>
             <button 
                onClick={handleGenerate}
                disabled={generateLessonMutation.isPending}
                className="px-8 py-3.5 bg-primary text-primary-foreground font-bold border border-transparent rounded-xl shadow-md shadow-primary/20 hover:bg-primary/90 transition-all flex items-center justify-center gap-2 mx-auto disabled:opacity-70 disabled:hover:bg-primary"
             >
               {generateLessonMutation.isPending ? (
                 <>
                   <Loader2 className="w-5 h-5 animate-spin" />
                   Генерация (15-30 сек)...
                 </>
               ) : (
                 <>
                   <Sparkles className="w-5 h-5" />
                   Сгенерировать AI
                 </>
               )}
             </button>
          </div>
        )}
      </div>
    </div>
  );
}
