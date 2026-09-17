import { useState } from 'react';
import { useSections, useTopics, type Section } from '@/lib/api';
import { useParams, Link } from 'wouter';
import { ChevronDown, PlayCircle, Clock, Loader2, ArrowLeft, ChevronRight } from 'lucide-react';

function SectionItem({ section, isFirst }: { section: Section, isFirst: boolean }) {
  const [expanded, setExpanded] = useState(isFirst);
  const { data: topics, isLoading } = useTopics(section.id, expanded);

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
          {isLoading ? (
            <div className="flex items-center justify-center py-6 text-muted-foreground">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : (
            topics?.map((topic) => (
              <Link key={topic.id} href={`/learn/${section.subject_id}/${topic.id}`}>
                <div className="group flex items-center justify-between p-4 md:p-5 rounded-2xl bg-card border border-border hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer">
                  <div className="flex items-center gap-5">
                    <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center flex-shrink-0 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                      <PlayCircle className="w-6 h-6" />
                    </div>
                    <div>
                      <div className="font-semibold text-foreground text-lg mb-1">{topic.name}</div>
                      <div className="flex items-center gap-3 text-sm text-muted-foreground font-medium">
                        <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" /> {topic.hours} ч</span>
                        <span className="px-2 py-0.5 bg-muted rounded">{topic.lesson_type}</span>
                      </div>
                    </div>
                  </div>
                  <ChevronRight className="w-5 h-5 text-muted-foreground opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-primary hidden md:block" />
                </div>
              </Link>
            ))
          )}
          {topics?.length === 0 && !isLoading && (
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
  const { data: sections, isLoading } = useSections(subjectId);

  if (isLoading) return <div className="flex justify-center p-12"><Loader2 className="w-8 h-8 animate-spin text-primary/50" /></div>;

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <Link href="/learn" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Назад к предметам
        </Link>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Программа курса</h1>
        <p className="text-muted-foreground mt-2 font-medium">Изучайте материалы последовательно</p>
      </div>

      <div className="space-y-6">
        {sections?.map((section, idx) => (
          <SectionItem key={section.id} section={section} isFirst={idx === 0} />
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
