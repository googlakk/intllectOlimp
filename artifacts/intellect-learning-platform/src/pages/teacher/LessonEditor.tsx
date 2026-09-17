import { useParams, Link } from 'wouter';
import { AlertTriangle, ArrowLeft, Loader2, Sparkles, Globe, EyeOff } from 'lucide-react';
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

  const blocks = lesson?.blocks || [];
  const isPublished = lesson?.status === 'published';

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
      publishLessonMutation.mutate({ lesson_id: lesson.id, teacher_id: user.id }, {
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
              disabled={publishLessonMutation.isPending || unpublishLessonMutation.isPending}
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
        {isLoadingLesson ? (
          <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
            <Loader2 className="w-8 h-8 animate-spin mb-4 text-primary" />
            <p className="font-medium">Загрузка урока...</p>
          </div>
        ) : blocks.length > 0 ? (
          <div>
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
