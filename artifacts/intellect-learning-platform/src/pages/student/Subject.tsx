import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  getStudentLessonManifest,
  lessonManifestQueryKey,
  useCurriculumMap,
  useSections,
  type CurriculumMapTopic,
  type Section,
} from '@/lib/api';
import { useAuth } from '@/components/auth/AuthContext';
import { useParams, Link } from 'wouter';
import { ChevronDown, PlayCircle, Clock, Loader2, ArrowLeft, ChevronRight, BookOpen, CheckCircle2, Sparkles, RotateCcw, Hourglass } from 'lucide-react';

function SectionItem({
  section,
  isFirst,
  topics,
  studentId,
}: {
  section: Section,
  isFirst: boolean,
  topics: CurriculumMapTopic[],
  studentId: number,
}) {
  const [expanded, setExpanded] = useState(isFirst);
  const queryClient = useQueryClient();
  const prefetchLesson = (topicId: number) => {
    if (!studentId) return;
    void queryClient.prefetchQuery({
      queryKey: lessonManifestQueryKey(topicId, studentId),
      queryFn: () => getStudentLessonManifest(topicId),
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
    });
  };

  return (
    <div className="border border-border rounded-3xl bg-card overflow-hidden transition-all duration-300 shadow-sm">
      <button 
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-6 bg-card hover:bg-muted/30 transition-colors"
      >
        <div className="flex flex-col items-start text-left">
          <div className="text-sm font-bold text-primary mb-1 uppercase tracking-wider">Раздел {section.sort_order}</div>
          <h3 className="text-xl font-bold text-foreground">{section.name}</h3>
        </div>
        <div className="flex items-center gap-4 text-muted-foreground">
          <span className="text-sm font-semibold px-4 py-1.5 bg-muted rounded-full hidden sm:block">
            {section.total_hours} часов
          </span>
          <ChevronDown className={`w-5 h-5 transition-transform duration-300 ${expanded ? 'rotate-180 text-primary' : ''}`} />
        </div>
      </button>
      
      {expanded && (
        <div className="border-t border-border bg-muted/10 p-4 md:p-6 space-y-3">
          {topics.map((topic) => {
            const locked = topic.state === 'locked';
            const mastered = topic.state === 'mastered';
            const needsPractice = topic.mastery_status === 'needs_practice' && topic.attempts > 0;
            const lessonReady = topic.lesson_status === 'published';
            const clickable = lessonReady;
            const statusLabel = mastered
              ? 'Освоено'
              : needsPractice
                ? 'Повторить'
                : topic.state === 'in_progress'
                  ? 'Продолжить'
                  : !lessonReady
                    ? 'Готовится'
                    : locked
                      ? 'Можно пройти'
                      : topic.state === 'available'
                      ? 'Начать'
                      : 'Начать';
            const content = (
                <div className={`group flex items-center justify-between p-4 md:p-5 rounded-xl border transition-all ${!clickable ? 'border-border bg-muted/30 text-muted-foreground' : 'bg-card border-border hover:border-primary/40 hover:shadow-sm cursor-pointer'}`}>
                  <div className="flex items-center gap-5">
                    <div className={`w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 transition-colors ${mastered ? 'bg-emerald-500/10 text-emerald-600' : needsPractice || (locked && lessonReady) ? 'bg-amber-500/10 text-amber-700' : !clickable ? 'bg-muted text-muted-foreground' : 'bg-primary/10 text-primary group-hover:bg-primary group-hover:text-primary-foreground'}`}>
                      {mastered ? <CheckCircle2 className="w-6 h-6" /> : needsPractice ? <RotateCcw className="w-5 h-5" /> : !lessonReady ? <Hourglass className="w-5 h-5" /> : <PlayCircle className="w-6 h-6" />}
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold text-foreground text-lg mb-1">{topic.name}</div>
                      <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground font-medium">
                        <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" /> {topic.hours} ч</span>
                        <span className={`px-2 py-0.5 rounded ${mastered ? 'bg-emerald-500/10 text-emerald-700' : needsPractice || (locked && lessonReady) ? 'bg-amber-500/10 text-amber-700' : topic.state === 'available' && lessonReady ? 'bg-primary/10 text-primary' : 'bg-muted'}`}>
                          {statusLabel}
                        </span>
                      </div>
                      <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{topic.reason}</p>
                    </div>
                  </div>
                  {clickable && <ChevronRight className="w-5 h-5 text-muted-foreground opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-primary hidden md:block" />}
                </div>
            );
            return clickable ? (
              <Link
                key={topic.id}
                href={`/learn/${section.subject_id}/${topic.id}`}
                onFocus={() => prefetchLesson(topic.id)}
                onMouseEnter={() => prefetchLesson(topic.id)}
                onTouchStart={() => prefetchLesson(topic.id)}
              >
                {content}
              </Link>
            ) : <div key={topic.id}>{content}</div>;
          })}
          {topics.length === 0 && (
            <div className="text-center py-6 text-muted-foreground text-sm font-medium">
              Темы пока не добавлены
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SubjectView() {
  const params = useParams();
  const subjectId = Number(params.subjectId);
  const { user } = useAuth();
  const studentId = user?.id ?? 0;
  const { data: sections, isLoading, isError } = useSections(subjectId, studentId > 0, studentId || undefined);
  const curriculum = useCurriculumMap(studentId, subjectId, studentId > 0);

  if (isLoading || curriculum.isLoading) return <div className="flex justify-center p-12"><Loader2 className="w-8 h-8 animate-spin text-primary/50" /></div>;

  if (isError || curriculum.isError) {
    return (
      <div className="mx-auto max-w-2xl py-16 text-center">
        <BookOpen className="mx-auto mb-5 h-12 w-12 text-muted-foreground" />
        <h1 className="text-2xl font-bold text-foreground">Предмет недоступен</h1>
        <p className="mt-2 text-muted-foreground">Этот курс относится к другому классу.</p>
        <Link href="/learn" className="mt-6 inline-flex items-center gap-2 font-semibold text-primary">
          <ArrowLeft className="h-4 w-4" /> Вернуться к своим предметам
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <Link href="/learn" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Назад к предметам
        </Link>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Программа курса</h1>
        <p className="text-muted-foreground mt-2 font-medium">Осваивайте навыки и открывайте новые маршруты по программе</p>
        {(curriculum.data?.topics.some((topic) => topic.unlocked_by_topic_id) ?? false) && (
          <div className="mt-5 flex items-start gap-3 rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm text-foreground">
            <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div><strong>Варп-врата активны.</strong> Некоторые темы доступны раньше обычной последовательности, потому что нужные навыки уже подтверждены.</div>
          </div>
        )}
      </div>

      <div className="space-y-6">
        {sections?.map((section, idx) => (
          <SectionItem
            key={section.id}
            section={section}
            isFirst={idx === 0}
            studentId={studentId}
            topics={(curriculum.data?.topics ?? []).filter((topic) => topic.section_id === section.id)}
          />
        ))}
        {sections?.length === 0 && (
           <div className="text-center py-16 bg-card rounded-3xl border border-dashed border-border">
             <p className="text-muted-foreground font-medium text-lg">Программа формируется</p>
           </div>
        )}
      </div>
    </div>
  );
}
