import { useParams, Link } from 'wouter';
import { ArrowLeft, Save, Plus, LayoutTemplate, MessageSquare, PlaySquare, HelpCircle, FileText } from 'lucide-react';

export default function LessonEditor() {
  const { topicId } = useParams();

  return (
    <div className="max-w-6xl mx-auto h-[calc(100vh-8rem)] flex flex-col">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8 shrink-0">
        <div>
          <Link href="/dashboard/lessons" className="inline-flex items-center gap-2 text-sm font-bold text-muted-foreground hover:text-foreground mb-3 transition-colors">
            <ArrowLeft className="w-4 h-4" /> Назад к темам
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-3">
            Редактор урока <span className="text-sm font-mono font-bold bg-muted text-muted-foreground px-2.5 py-1 rounded-lg">ID: {topicId}</span>
          </h1>
        </div>
        <div className="flex gap-3">
          <button className="px-6 py-2.5 text-sm font-bold rounded-xl bg-card border border-border text-foreground hover:bg-muted transition-colors shadow-sm">
            Предпросмотр
          </button>
          <button className="px-6 py-2.5 text-sm font-bold rounded-xl bg-primary text-primary-foreground shadow-md shadow-primary/20 hover:bg-primary/90 transition-colors flex items-center gap-2">
            <Save className="w-4 h-4" /> Сохранить
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col md:flex-row gap-6 min-h-0">
        {/* Toolbar */}
        <div className="w-full md:w-72 shrink-0 bg-card rounded-[2rem] border border-border shadow-sm p-5 flex flex-col gap-2 overflow-y-auto custom-scrollbar">
          <div className="text-xs font-extrabold text-muted-foreground uppercase tracking-wider mb-4 px-2">Педагогические блоки</div>
          {[
            { icon: FileText, label: 'Теория (Текст)' },
            { icon: PlaySquare, label: 'Видеоматериал' },
            { icon: MessageSquare, label: 'Диалог/Пример' },
            { icon: HelpCircle, label: 'Тестовое задание' },
            { icon: LayoutTemplate, label: 'Интерактив' },
          ].map((btn, i) => (
            <button key={i} className="flex items-center gap-4 p-4 rounded-2xl border border-transparent hover:border-border hover:bg-muted/50 text-left transition-all text-sm font-bold text-foreground group">
              <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                <btn.icon className="w-4 h-4" />
              </div>
              {btn.label}
              <Plus className="w-4 h-4 ml-auto opacity-0 group-hover:opacity-100 text-primary transition-opacity" />
            </button>
          ))}
        </div>

        {/* Canvas */}
        <div className="flex-1 bg-muted/30 rounded-[2rem] border-2 border-dashed border-border/80 p-8 flex flex-col items-center justify-center text-center overflow-y-auto custom-scrollbar relative group hover:border-primary/30 transition-colors">
           <div className="absolute inset-0 bg-[radial-gradient(#e5e7eb_1px,transparent_1px)] [background-size:20px_20px] opacity-40"></div>
           
           <div className="relative z-10 max-w-sm">
             <div className="w-20 h-20 bg-card border border-border rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-sm group-hover:scale-105 transition-transform">
               <LayoutTemplate className="w-10 h-10 text-muted-foreground/40 text-primary" />
             </div>
             <h3 className="text-2xl font-bold text-foreground mb-3">Урок пока пуст</h3>
             <p className="text-muted-foreground text-sm mb-8 font-medium">
               Перетащите блоки из панели слева или нажмите на них, чтобы начать создание структуры занятия.
             </p>
             <button className="px-8 py-3.5 bg-card text-primary font-bold border border-primary/20 rounded-xl shadow-sm hover:border-primary hover:bg-primary/5 transition-all flex items-center justify-center gap-2 mx-auto">
               <Plus className="w-5 h-5" /> Добавить первый блок
             </button>
           </div>
        </div>
      </div>
    </div>
  );
}
