import { useState } from 'react';
import { useSubjectTopics, useQuarters, currentQuarterNumber, type SubjectTopic } from '@/lib/api';
import { useParams, Link } from 'wouter';
import { PlayCircle, Clock, Loader2, ArrowLeft, ChevronRight } from 'lucide-react';

const QUARTERS = [1, 2, 3, 4];

type LearningTopic = SubjectTopic & { totalHours: number };

// Repeated KTP rows of one topic are one learning topic for the student.
function learningTopics(topics: SubjectTopic[]): LearningTopic[] {
  const extraHours = new Map<number, number>();
  for (const t of topics) {
    if (t.lesson_topic_id) extraHours.set(t.lesson_topic_id, (extraHours.get(t.lesson_topic_id) ?? 0) + (t.hours || 0));
  }
  return topics
    .filter((t) => !t.lesson_topic_id)
    .map((t) => ({ ...t, totalHours: (t.hours || 0) + (extraHours.get(t.id) ?? 0) }));
}

function TopicLink({ topic, subjectId }: { topic: LearningTopic; subjectId: number }) {
  const parts = Math.min(4, Math.max(1, topic.totalHours));
  return (
    <Link href={`/learn/${subjectId}/${topic.id}`}>
      <div className="group flex items-center justify-between p-4 md:p-5 rounded-2xl bg-card border border-border hover:border-primary/40 hover:shadow-sm transition-all cursor-pointer">
        <div className="flex items-center gap-5">
          <div className="w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center flex-shrink-0 group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
            <PlayCircle className="w-6 h-6" />
          </div>
          <div>
            <div className="font-semibold text-foreground text-lg mb-1">{topic.name}</div>
            <div className="flex items-center gap-3 text-sm text-muted-foreground font-medium">
              <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" /> ~{parts * 10} мин</span>
              {parts > 1 && <span className="px-2 py-0.5 bg-muted rounded">{parts} шага</span>}
            </div>
          </div>
        </div>
        <ChevronRight className="w-5 h-5 opacity-0 -translate-x-4 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-primary hidden md:block" />
      </div>
    </Link>
  );
}

export default function SubjectView() {
  const params = useParams();
  const subjectId = Number(params.subjectId);
  const { data: topics, isLoading } = useSubjectTopics(subjectId);
  const { data: quarters } = useQuarters();
  const [quarter, setQuarter] = useState<number | null>(null);
  const activeQuarter = quarter ?? currentQuarterNumber(quarters);

  if (isLoading) return <div className="flex justify-center p-12"><Loader2 className="w-8 h-8 animate-spin text-primary/50" /></div>;

  const all = learningTopics(topics ?? []);
  // Topics without a quarter (old KTP uploads) stay visible in the first tab.
  const shown = all.filter((t) => (t.quarter ?? 1) === activeQuarter);
  const sections: Array<{ key: number; name: string; order: number; topics: LearningTopic[] }> = [];
  for (const topic of shown) {
    const last = sections[sections.length - 1];
    if (last && last.key === topic.section_id) last.topics.push(topic);
    else sections.push({ key: topic.section_id, name: topic.section_name, order: topic.section_sort_order, topics: [topic] });
  }

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <Link href="/learn" className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Назад к предметам
        </Link>
        <h1 className="text-3xl font-bold tracking-tight text-foreground">Программа курса</h1>
        <p className="text-muted-foreground mt-2 font-medium">Короткие уроки по темам — изучайте по порядку</p>
      </div>

      <div className="flex gap-2 overflow-x-auto pb-1">
        {QUARTERS.map((n) => (
          <button
            key={n}
            onClick={() => setQuarter(n)}
            className={`px-5 py-2.5 rounded-xl font-bold text-sm whitespace-nowrap transition-all ${
              activeQuarter === n ? 'bg-primary text-primary-foreground shadow-md' : 'bg-card border border-border text-muted-foreground hover:text-foreground'
            }`}
          >
            {n} четверть
          </button>
        ))}
      </div>

      <div className="space-y-6">
        {sections.map((section) => (
          <div key={section.key} className="border border-border rounded-3xl bg-card overflow-hidden shadow-sm">
            <div className="p-6">
              <div className="text-sm font-bold text-primary mb-1 uppercase tracking-wider">Раздел {section.order}</div>
              <h3 className="text-xl font-bold text-foreground">{section.name}</h3>
            </div>
            <div className="border-t border-border bg-muted/10 p-4 md:p-6 space-y-3">
              {section.topics.map((topic) => <TopicLink key={topic.id} topic={topic} subjectId={subjectId} />)}
            </div>
          </div>
        ))}
        {sections.length === 0 && (
          <div className="text-center py-16 bg-card rounded-3xl border border-dashed border-border">
            <p className="text-muted-foreground font-medium text-lg">
              {all.length === 0 ? 'Программа формируется' : 'В этой четверти тем нет'}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
