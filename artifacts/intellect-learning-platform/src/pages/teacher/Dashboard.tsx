import { Users, BookOpen, Layers, Activity, Search } from 'lucide-react';
import { useDashboardOverview, useDashboardStudents } from '@/lib/api';

export default function Dashboard() {
  const { data: overviewData } = useDashboardOverview();
  const { data: studentData } = useDashboardStudents();
  const overview = overviewData ?? {
    students: 142,
    subjects: 5,
    topics: 84,
    published_lessons: 32,
    average_progress: 48
  };

  const students = studentData ?? [];

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Обзор платформы</h1>
        <p className="text-muted-foreground mt-2 font-medium">Ключевые показатели и активность учеников</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-6">
        {[
           { label: 'Всего учеников', val: overview.students, icon: Users, color: 'text-blue-500', bg: 'bg-blue-500/10' },
           { label: 'Готовых уроков', val: overview.published_lessons, icon: BookOpen, color: 'text-indigo-500', bg: 'bg-indigo-500/10' },
           { label: 'Тем в базе', val: overview.topics, icon: Layers, color: 'text-purple-500', bg: 'bg-purple-500/10' },
           { label: 'Средний прогресс', val: `${overview.average_progress}%`, icon: Activity, color: 'text-emerald-500', bg: 'bg-emerald-500/10' },
        ].map((s, i) => (
          <div key={i} className="bg-card p-6 rounded-3xl border border-border shadow-sm flex items-center gap-5 hover:border-primary/20 transition-colors">
            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center ${s.bg} ${s.color}`}>
              <s.icon className="w-6 h-6" />
            </div>
            <div>
              <div className="text-2xl font-bold text-foreground">{s.val}</div>
              <div className="text-sm font-semibold text-muted-foreground mt-0.5">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-card rounded-[2rem] border border-border shadow-sm overflow-hidden">
        <div className="p-6 md:p-8 border-b border-border/50 flex flex-col sm:flex-row sm:items-center justify-between gap-6">
          <h2 className="text-xl font-bold text-foreground">Успеваемость учеников</h2>
          <div className="relative w-full sm:w-80">
            <Search className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input 
              type="text" 
              placeholder="Поиск по имени..." 
              className="w-full pl-11 pr-4 py-2.5 bg-muted/50 border border-border rounded-xl text-sm focus:outline-none focus:border-primary/50 focus:bg-card transition-colors font-medium"
            />
          </div>
        </div>
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-sm text-left whitespace-nowrap">
            <thead className="bg-muted/20 text-muted-foreground font-bold">
              <tr>
                <th className="px-8 py-5">Имя ученика</th>
                <th className="px-8 py-5 text-center">Класс</th>
                <th className="px-8 py-5 text-center">Пройдено тем</th>
                <th className="px-8 py-5 text-center">Средний балл</th>
                <th className="px-8 py-5"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/50">
              {students.map((student) => (
                <tr key={student.id} className="hover:bg-muted/10 transition-colors">
                  <td className="px-8 py-5 font-bold text-foreground">{student.name}</td>
                  <td className="px-8 py-5 text-center font-medium text-muted-foreground">{student.grade}</td>
                  <td className="px-8 py-5 text-center text-foreground font-bold">{student.completed_topics}</td>
                  <td className="px-8 py-5 text-center">
                    <span className={`inline-flex items-center justify-center px-3 py-1 rounded-full font-bold ${
                      student.average_score >= 90 ? 'bg-emerald-500/10 text-emerald-600' :
                      student.average_score >= 70 ? 'bg-blue-500/10 text-blue-600' :
                      'bg-amber-500/10 text-amber-600'
                    }`}>
                      {student.average_score}
                    </span>
                  </td>
                  <td className="px-8 py-5 text-right">
                    <button className="text-primary hover:text-primary/80 font-bold transition-colors">Подробнее</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
