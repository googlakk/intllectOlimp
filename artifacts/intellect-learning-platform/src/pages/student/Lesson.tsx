import { useParams, Link } from 'wouter';
import { ArrowLeft, BookOpen, Code, Lightbulb, PlayCircle } from 'lucide-react';

export default function Lesson() {
  const params = useParams();
  const subjectId = params.subjectId;

  return (
    <div className="max-w-5xl mx-auto">
      <Link href={`/learn/${subjectId}`} className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground mb-8 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Назад к программе
      </Link>
      
      <div className="bg-card rounded-[2rem] border border-border shadow-sm overflow-hidden">
        <div className="h-48 bg-gradient-to-br from-primary/10 via-primary/5 to-transparent relative p-8 flex flex-col justify-end border-b border-border/50">
          <div className="absolute top-6 right-6 px-4 py-1.5 bg-card/80 backdrop-blur-sm rounded-full shadow-sm text-sm font-bold text-primary flex items-center gap-2 border border-border/50">
            <div className="w-2.5 h-2.5 rounded-full bg-primary animate-pulse"></div>
            Изучение
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold text-foreground mt-4 mb-2 leading-tight">Теория графов: Введение</h1>
          <p className="text-muted-foreground font-semibold flex items-center gap-4 text-sm">
            <span>Математика</span>
            <span>•</span>
            <span>2 часа</span>
          </p>
        </div>

        <div className="p-6 md:p-10 space-y-12">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { icon: Lightbulb, title: "Цели урока", desc: "Понять основные определения и теоремы." },
              { icon: BookOpen, title: "Материалы", desc: "Конспект, интерактивные задания." },
              { icon: Code, title: "Практика", desc: "Решение 5 олимпиадных задач." }
            ].map((it, i) => (
              <div key={i} className="bg-muted/40 rounded-3xl p-6 md:p-8 border border-transparent hover:border-primary/20 transition-colors">
                <it.icon className="w-8 h-8 text-primary mb-4" />
                <h3 className="font-bold text-lg text-foreground mb-2">{it.title}</h3>
                <p className="text-sm text-muted-foreground font-medium">{it.desc}</p>
              </div>
            ))}
          </div>

          <div className="text-center py-20 border-2 border-dashed border-border rounded-3xl bg-muted/10 px-4">
            <PlayCircle className="w-16 h-16 text-muted-foreground/30 mx-auto mb-6" />
            <h3 className="text-2xl font-bold text-foreground mb-3">Урок загружается</h3>
            <p className="text-muted-foreground max-w-md mx-auto font-medium">
              Здесь будет отображаться интерактивный плеер блоков: видео, тексты, квизы и задачи с автопроверкой.
            </p>
            <button className="mt-10 px-8 py-3.5 bg-primary text-primary-foreground font-bold rounded-xl shadow-lg shadow-primary/30 hover:bg-primary/90 hover:-translate-y-0.5 transition-all">
              Завершить урок
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
