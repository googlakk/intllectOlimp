import { Trophy, Target, BookOpen, Flame, Brain, ArrowUpRight } from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';

export default function Progress() {
  const { user } = useAuth();
  
  const stats = [
    { label: 'Решено задач', value: '142', icon: Target, color: 'text-blue-500', bg: 'bg-blue-500/10' },
    { label: 'Пройдено тем', value: '28', icon: BookOpen, color: 'text-indigo-500', bg: 'bg-indigo-500/10' },
    { label: 'Рейтинг', value: 'Топ 5%', icon: Trophy, color: 'text-amber-500', bg: 'bg-amber-500/10' },
    { label: 'Серия дней', value: '12', icon: Flame, color: 'text-orange-500', bg: 'bg-orange-500/10' },
  ];

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Мой прогресс</h1>
        <p className="text-muted-foreground mt-2 font-medium">Статистика вашего обучения и достижения</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6">
        {stats.map((stat, i) => (
          <div key={i} className="bg-card p-6 md:p-8 rounded-3xl border border-border shadow-sm flex flex-col items-center text-center hover:shadow-md hover:border-primary/20 transition-all cursor-default">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-5 ${stat.bg} ${stat.color}`}>
              <stat.icon className="w-7 h-7" />
            </div>
            <div className="text-3xl font-extrabold text-foreground mb-1.5">{stat.value}</div>
            <div className="text-sm font-semibold text-muted-foreground">{stat.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-8">
        <div className="bg-card p-6 md:p-10 rounded-[2rem] border border-border shadow-sm">
          <h3 className="text-xl font-bold text-foreground mb-8 flex items-center gap-3">
            <Brain className="w-6 h-6 text-primary" /> Мастерство по предметам
          </h3>
          <div className="space-y-8">
            {[
              { name: 'Математика', prog: 75, grade: 'Продвинутый' },
              { name: 'Информатика', prog: 45, grade: 'Базовый' },
              { name: 'Физика', prog: 60, grade: 'Средний' }
            ].map(s => (
              <div key={s.name}>
                <div className="flex justify-between text-sm mb-3">
                  <span className="font-bold text-foreground text-base">{s.name}</span>
                  <span className="font-semibold text-muted-foreground">{s.grade}</span>
                </div>
                <div className="h-3 w-full bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full transition-all duration-1000" style={{ width: `${s.prog}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-gradient-to-br from-primary/5 to-transparent p-6 md:p-10 rounded-[2rem] border border-border shadow-sm flex flex-col justify-center items-center text-center">
           <Trophy className="w-24 h-24 text-primary mb-8 opacity-90 drop-shadow-md" />
           <h3 className="text-2xl font-bold text-foreground mb-3">Ближайшая цель</h3>
           <p className="text-muted-foreground mb-8 max-w-sm font-medium leading-relaxed">
             Завершите еще 2 темы по математике, чтобы получить достижение «Аналитик».
           </p>
           <button className="flex items-center gap-2 px-8 py-3.5 bg-card border border-primary/20 text-primary font-bold rounded-xl shadow-sm hover:bg-primary hover:text-primary-foreground hover:border-primary transition-all">
             Продолжить обучение <ArrowUpRight className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
