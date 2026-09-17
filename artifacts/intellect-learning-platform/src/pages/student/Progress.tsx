import { Trophy, Target, BookOpen, Brain, Loader2 } from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { useGetStudentProgress } from '@/lib/api';

export default function Progress() {
  const { user } = useAuth();
  const { data: progress = [], isLoading } = useGetStudentProgress(user?.id || 0, !!user?.id);
  const completed = progress.filter((item) => item.status === 'completed').length;
  const mastered = progress.filter((item) => item.mastery_status === 'mastered').length;
  const objectiveResults = progress.flatMap((item) => Object.values(item.objective_mastery || {}));
  const masteredObjectives = objectiveResults.filter((item) => item.status === 'mastered').length;
  const needsPractice = objectiveResults.filter((item) => item.status === 'needs_practice').length;
  const average = progress.length ? Math.round(progress.reduce((sum, item) => sum + (item.score || 0), 0) / progress.length) : null;
  const stats = [
    { label: 'Завершено уроков', value: String(completed), icon: BookOpen, color: 'text-indigo-500', bg: 'bg-indigo-500/10' },
    { label: 'Освоено целей', value: String(masteredObjectives), icon: Target, color: 'text-blue-500', bg: 'bg-blue-500/10' },
    { label: 'Уроков с мастерством', value: String(mastered), icon: Trophy, color: 'text-amber-500', bg: 'bg-amber-500/10' },
    { label: 'Средний результат', value: average === null ? '—' : `${average}%`, icon: Brain, color: 'text-primary', bg: 'bg-primary/10' },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Мой прогресс</h1>
        <p className="text-muted-foreground mt-2 font-medium">Статистика вашего обучения и достижения</p>
      </div>

      {isLoading ? (
        <div data-testid="progress-loading" className="flex items-center justify-center rounded-3xl border border-border bg-card py-16 text-muted-foreground"><Loader2 className="mr-3 h-6 w-6 animate-spin" />Загружаем реальные результаты…</div>
      ) : <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
        {stats.map((stat, i) => (
          <div key={i} className="bg-card p-6 md:p-8 rounded-3xl border border-border shadow-sm flex flex-col items-center text-center hover:shadow-md hover:border-primary/20 transition-all cursor-default">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-5 ${stat.bg} ${stat.color}`}>
              <stat.icon className="w-7 h-7" />
            </div>
            <div className="text-3xl font-extrabold text-foreground mb-1.5">{stat.value}</div>
            <div className="text-sm font-semibold text-muted-foreground">{stat.label}</div>
          </div>
        ))}
      </div>}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        <div className="bg-card p-6 md:p-10 rounded-[2rem] border border-border shadow-sm">
          <h3 className="text-xl font-bold text-foreground mb-8 flex items-center gap-3">
            <Brain className="w-6 h-6 text-primary" /> Мастерство по предметам
          </h3>
          <div className="space-y-8">
            {progress.length === 0 ? (
              <p data-testid="progress-empty" className="text-muted-foreground">Пока нет завершённых уроков с измеренными результатами.</p>
            ) : (
              <div className="space-y-3 text-sm text-muted-foreground">
                <p>Освоено целей: <strong className="text-foreground">{masteredObjectives}</strong></p>
                <p>Целей требуют практики: <strong className="text-foreground">{needsPractice}</strong></p>
                <p>Результаты рассчитаны по сохранённым ответам, а не по демонстрационным показателям.</p>
              </div>
            )}
          </div>
        </div>

        <div className="bg-gradient-to-br from-primary/5 to-transparent p-6 md:p-10 rounded-[2rem] border border-border shadow-sm flex flex-col justify-center items-center text-center">
           <Trophy className="w-24 h-24 text-primary mb-8 opacity-90 drop-shadow-md" />
           <h3 className="text-2xl font-bold text-foreground mb-3">Следующая цель</h3>
           <p className="text-muted-foreground max-w-sm font-medium leading-relaxed">
              {needsPractice > 0 ? 'Вернитесь к целям, которым нужна дополнительная практика.' : 'Завершите урок с измеренными целями, чтобы увидеть следующий результат.'}
           </p>
        </div>
      </div>
    </div>
  );
}
