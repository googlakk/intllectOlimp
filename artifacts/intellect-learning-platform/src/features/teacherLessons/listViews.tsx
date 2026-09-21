import { Link } from 'wouter';
import { BookOpen, Edit3, Loader2 } from 'lucide-react';
import { useSubjectOutline, type SectionOutline, type Subject, type Topic } from '@/lib/api';
import { lessonStatusView, lessonTypeLabel } from './listModel';

type SubjectTabsProps = {
  isLoading: boolean;
  selectedSubject: number | null;
  subjects: Subject[] | undefined;
  onSelect: (subjectId: number) => void;
};

export function SubjectTabs({ isLoading, selectedSubject, subjects, onSelect }: SubjectTabsProps) {
  return (
    <div className="flex gap-3 overflow-x-auto pb-4 custom-scrollbar">
      {isLoading ? (
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      ) : (
        subjects?.map((subject) => (
          <button
            key={subject.id}
            onClick={() => onSelect(subject.id)}
            className={`px-6 py-3 rounded-xl font-bold whitespace-nowrap transition-all ${
              selectedSubject === subject.id
                ? 'bg-primary text-primary-foreground shadow-md'
                : 'bg-card border border-border text-muted-foreground hover:border-primary/30 hover:text-foreground'
            }`}
          >
            {subject.name}
          </button>
        ))
      )}
    </div>
  );
}

export function NoSubjectSelected() {
  return (
    <div className="py-24 text-center text-muted-foreground bg-card rounded-[2rem] border border-dashed border-border/80">
      <BookOpen className="w-16 h-16 mx-auto mb-6 opacity-40 text-primary" />
      <p className="text-xl font-bold text-foreground mb-2">Выберите предмет</p>
      <p className="text-sm font-medium">Для просмотра и редактирования структуры курса</p>
    </div>
  );
}

export function SectionsList({ subjectId }: { subjectId: number }) {
  const { data: sections, isLoading } = useSubjectOutline(subjectId);

  if (isLoading) {
    return (
      <div className="py-12 flex justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {sections?.map((section) => (
        <div key={section.id} className="bg-card rounded-[2rem] border border-border shadow-sm overflow-hidden">
          <div className="px-6 md:px-8 py-5 bg-muted/30 border-b border-border flex justify-between items-center">
            <h3 className="font-bold text-lg text-foreground uppercase tracking-wide text-primary">
              Раздел {section.sort_order}: {section.name}
            </h3>
            <span className="text-sm font-bold text-muted-foreground bg-card px-3 py-1 rounded-lg border border-border">
              {section.total_hours} часов
            </span>
          </div>
          <TopicsList section={section} />
        </div>
      ))}
    </div>
  );
}

function TopicsList({ section }: { section: SectionOutline }) {
  return (
    <div className="divide-y divide-border/50">
      {section.topics.map((topic) => (
        <TopicRow key={topic.id} topic={topic} />
      ))}
      {section.topics.length === 0 && (
        <div className="p-8 text-center text-sm font-medium text-muted-foreground">Нет тем в этом разделе</div>
      )}
    </div>
  );
}

function TopicRow({ topic }: { topic: Topic }) {
  const status = lessonStatusView(topic, false);

  return (
    <div className="p-6 md:px-8 flex flex-col md:flex-row md:items-start justify-between gap-4 hover:bg-muted/10 transition-colors">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-2">
          {topic.ktp_number && (
            <span className="text-xs font-mono font-bold bg-muted px-2 py-1 rounded text-muted-foreground">
              {topic.ktp_number}
            </span>
          )}
          <span className="font-bold text-foreground text-lg">{topic.name}</span>
          {status && (
            <span className={`text-xs font-bold px-2 py-1 rounded ${status.badgeClasses}`}>
              {status.badgeText}
            </span>
          )}
        </div>
        <div className="text-sm font-semibold text-muted-foreground flex items-center gap-4">
          <span className="bg-card border border-border px-2 py-0.5 rounded">{topic.hours} ч.</span>
          <span className="text-primary">{lessonTypeLabel(topic.lesson_type)}</span>
        </div>

        {topic.learning_objectives && (
          <div className="mt-3 text-sm text-foreground/80 leading-relaxed">
            <span className="font-bold text-muted-foreground">Цели обучения: </span>
            {topic.learning_objectives}
          </div>
        )}

        {topic.skills?.length > 0 && (
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            {topic.skills.map((skill, index) => (
              <span key={index} className="text-xs font-semibold bg-primary/10 text-primary px-2 py-0.5 rounded">
                {skill}
              </span>
            ))}
          </div>
        )}

        {topic.resources && (
          <div className="mt-2.5 text-xs text-muted-foreground leading-relaxed">
            <span className="font-bold">Ресурсы: </span>
            {topic.resources}
          </div>
        )}
      </div>
      <Link href={`/dashboard/lessons/${topic.id}`}>
        <button className="flex items-center justify-center gap-2 px-5 py-2.5 bg-primary/10 text-primary font-bold rounded-xl hover:bg-primary hover:text-primary-foreground transition-all text-sm w-full md:w-auto">
          <Edit3 className="w-4 h-4" />
          Редактировать
        </button>
      </Link>
    </div>
  );
}
