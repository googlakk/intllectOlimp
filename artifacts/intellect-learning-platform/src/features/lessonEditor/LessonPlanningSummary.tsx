import type { ReactNode } from 'react';
import { Boxes, Clock3, Layers3, WandSparkles } from 'lucide-react';
import type { GeneratedLesson } from '@/lib/api';
import { lessonPlanningSummary } from '@/features/lessons/lessonMetadata';

type LessonPlanningSummaryProps = {
  lesson: GeneratedLesson;
};

export default function LessonPlanningSummary({ lesson }: LessonPlanningSummaryProps) {
  const summary = lessonPlanningSummary(lesson);
  if (!summary) return null;

  const mediaText = summary.mediaPolicy === 'suggested'
    ? 'медиа полезно как дополнение'
    : 'медиа опционально';

  return (
    <section className="mb-8 rounded-2xl border border-border bg-muted/20 p-5">
      <div className="mb-4 flex items-center gap-2">
        <Layers3 className="h-5 w-5 text-primary" />
        <h2 className="text-lg font-bold text-foreground">Структура урока</h2>
      </div>
      <div className="grid gap-3 text-sm md:grid-cols-2">
        <PlanningPill icon={<Clock3 className="h-4 w-4" />} label="Объём" value={summary.volumeLabel} />
        <PlanningPill icon={<Boxes className="h-4 w-4" />} label="Форма" value={summary.shapeLabel} />
        <PlanningPill label="Цели" value={`${summary.objectiveCount || 0}`} />
        <PlanningPill label="Бюджет блоков" value={summary.blockRange || 'не задан'} />
        <PlanningPill icon={<WandSparkles className="h-4 w-4" />} label="OpenRouter media" value={mediaText} />
        {summary.modulePart && <PlanningPill label="Часть модуля" value={summary.modulePart} />}
      </div>
    </section>
  );
}

function PlanningPill({ icon, label, value }: { icon?: ReactNode; label: string; value: string }) {
  return (
    <div className="flex min-h-12 items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-3">
      <span className="flex items-center gap-2 text-muted-foreground">
        {icon}
        {label}
      </span>
      <span className="text-right font-bold text-foreground">{value}</span>
    </div>
  );
}
