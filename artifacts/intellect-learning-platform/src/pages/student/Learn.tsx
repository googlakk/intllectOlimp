import { recommendLearning } from '@/features/progress/learningRecommendations';
import { GardenLessonCard } from '@/features/visualLesson/GardenLessonCard';
import { useSubjects, useCurriculumMap } from '@/lib/api';
import { useAuth } from '@/components/auth/AuthContext';
import { Link } from 'wouter';
import { BookText, Loader2 } from 'lucide-react';

export default function Learn() {
  const { user } = useAuth();
  const { data: subjects, isLoading } = useSubjects(user?.id);

  const { data: curriculum } = useCurriculumMap(user?.id || 0);
  const recommendation = recommendLearning(curriculum?.topics ?? []);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-primary/50" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">
          Доступные предметы
        </h1>
        <p className="text-muted-foreground mt-2">
          {user?.grade
            ? `Программы до ${user.grade} класса включительно`
            : 'Выберите предмет из своей учебной программы'}
        </p>
      </div>

      {recommendation && <section className="rounded-2xl border border-primary/30 bg-primary/5 p-6 space-y-3" aria-label="Следующий шаг">
        <p className="text-sm font-semibold text-primary">Ваш следующий шаг</p>
        <h2 className="text-xl font-bold">{recommendation.topic.name}</h2>
        <p className="text-muted-foreground">{recommendation.reason}</p>
        <Link href={`/learn/${recommendation.topic.subject_id}/${recommendation.topic.id}`} className="inline-flex rounded-xl bg-primary px-5 py-3 font-semibold text-primary-foreground">{recommendation.action}</Link>
      </section>}
      <GardenLessonCard />
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {subjects?.map((subject) => (
          <Link key={subject.id} href={`/learn/${subject.id}`}>
            <div className="group bg-card rounded-3xl border border-border shadow-sm hover:shadow-md hover:border-primary/30 transition-all p-6 flex flex-col h-full cursor-pointer overflow-hidden relative">
              <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-bl-full -mr-8 -mt-8 transition-transform group-hover:scale-110"></div>
              
              <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-6 relative group-hover:bg-primary group-hover:text-primary-foreground transition-all">
                <BookText className="w-6 h-6" />
              </div>
              <h3 className="text-xl font-bold text-foreground mb-2 relative">{subject.name}</h3>
              <div className="text-sm text-muted-foreground font-medium mb-8 relative">
                {subject.grade} класс • {subject.hours_per_week} ч/нед
              </div>
              
              <div className="mt-auto relative">
                <div className="flex items-center justify-between text-sm mb-2">
                  <span className="font-semibold text-foreground">Прогресс</span>
                  <span className="text-primary font-bold">{subject.progress ?? 0}%</span>
                </div>
                <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                  <div 
                    className="h-full bg-primary transition-all duration-1000 ease-out"
                    style={{ width: `${subject.progress ?? 0}%` }}
                  />
                </div>
              </div>
            </div>
          </Link>
        ))}
      </div>
      {subjects?.length === 0 && (
        <div className="border border-dashed border-border bg-card px-6 py-14 text-center">
          <BookText className="mx-auto mb-4 h-10 w-10 text-muted-foreground" />
          <p className="font-semibold text-foreground">Для вашего класса предметы пока не добавлены</p>
          <p className="mt-1 text-sm text-muted-foreground">Учитель сможет добавить их через загрузку КТП.</p>
        </div>
      )}
    </div>
  );
}
