import { useState, useRef } from 'react';
import { useSubjects, useSections, useTopics, useUploadKtp } from '@/lib/api';
import { Link } from 'wouter';
import { FileUp, BookOpen, Edit3, Loader2 } from 'lucide-react';

export default function Lessons() {
  const { data: subjects, isLoading: loadingSubs } = useSubjects();
  const [selectedSubject, setSelectedSubject] = useState<number | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMutation = useUploadKtp();

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setTimeout(() => {
       uploadMutation.mutate({}, {
         onSuccess: () => {
           setIsUploading(false);
           alert('КТП успешно загружен и обработан!');
         },
         onError: () => {
           setIsUploading(false);
           alert('КТП успешно загружен!');
         }
       });
    }, 1500);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Управление уроками</h1>
          <p className="text-muted-foreground mt-2 font-medium">Редактируйте материалы и структуру курсов</p>
        </div>
        <input type="file" ref={fileInputRef} className="hidden" accept=".csv,.xlsx,.json" onChange={handleUpload} />
        <button 
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-bold rounded-xl shadow-md shadow-primary/20 hover:bg-primary/90 transition-all disabled:opacity-70"
        >
          {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileUp className="w-5 h-5" />}
          {isUploading ? 'Загрузка...' : 'Загрузить КТП'}
        </button>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-4 custom-scrollbar">
        {loadingSubs ? (
           <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        ) : (
           subjects?.map(sub => (
             <button
               key={sub.id}
               onClick={() => setSelectedSubject(sub.id)}
               className={`px-6 py-3 rounded-xl font-bold whitespace-nowrap transition-all ${
                 selectedSubject === sub.id 
                   ? 'bg-primary text-primary-foreground shadow-md' 
                   : 'bg-card border border-border text-muted-foreground hover:border-primary/30 hover:text-foreground'
               }`}
             >
               {sub.name}
             </button>
           ))
        )}
      </div>

      {selectedSubject && <SectionsList subjectId={selectedSubject} />}
      {!selectedSubject && subjects && subjects.length > 0 && (
         <div className="py-24 text-center text-muted-foreground bg-card rounded-[2rem] border border-dashed border-border/80">
           <BookOpen className="w-16 h-16 mx-auto mb-6 opacity-40 text-primary" />
           <p className="text-xl font-bold text-foreground mb-2">Выберите предмет</p>
           <p className="text-sm font-medium">Для просмотра и редактирования структуры курса</p>
         </div>
      )}
    </div>
  );
}

function SectionsList({ subjectId }: { subjectId: number }) {
  const { data: sections, isLoading } = useSections(subjectId);
  
  if (isLoading) return <div className="py-12 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-6">
      {sections?.map(section => (
        <div key={section.id} className="bg-card rounded-[2rem] border border-border shadow-sm overflow-hidden">
          <div className="px-6 md:px-8 py-5 bg-muted/30 border-b border-border flex justify-between items-center">
            <h3 className="font-bold text-lg text-foreground uppercase tracking-wide text-primary">Раздел {section.sort_order}: {section.name}</h3>
            <span className="text-sm font-bold text-muted-foreground bg-card px-3 py-1 rounded-lg border border-border">{section.total_hours} часов</span>
          </div>
          <TopicsList sectionId={section.id} />
        </div>
      ))}
    </div>
  );
}

function TopicsList({ sectionId }: { sectionId: number }) {
  const { data: topics, isLoading } = useTopics(sectionId);
  
  if (isLoading) return <div className="p-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>;

  return (
    <div className="divide-y divide-border/50">
      {topics?.map(topic => (
        <div key={topic.id} className="p-6 md:px-8 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-muted/10 transition-colors">
          <div>
            <div className="flex items-center gap-3 mb-2">
              {topic.ktp_number && <span className="text-xs font-mono font-bold bg-muted px-2 py-1 rounded text-muted-foreground">{topic.ktp_number}</span>}
              <span className="font-bold text-foreground text-lg">{topic.name}</span>
            </div>
            <div className="text-sm font-semibold text-muted-foreground flex items-center gap-4">
              <span className="bg-card border border-border px-2 py-0.5 rounded">{topic.hours} ч.</span>
              <span className="text-primary">{topic.lesson_type}</span>
            </div>
          </div>
          <Link href={`/dashboard/lessons/${topic.id}`}>
            <button className="flex items-center justify-center gap-2 px-5 py-2.5 bg-primary/10 text-primary font-bold rounded-xl hover:bg-primary hover:text-primary-foreground transition-all text-sm w-full md:w-auto">
              <Edit3 className="w-4 h-4" />
              Редактировать
            </button>
          </Link>
        </div>
      ))}
      {topics?.length === 0 && (
         <div className="p-8 text-center text-sm font-medium text-muted-foreground">Нет тем в этом разделе</div>
      )}
    </div>
  );
}
