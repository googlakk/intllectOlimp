import { useState } from 'react';
import { CreateSection } from './CreateCourse';
import TopicForm from './TopicForm';
import { useArchiveTopic, useTeacherOutline } from '@/lib/api';
import { Link } from 'wouter';
import { useQueryClient } from '@tanstack/react-query';
import { BookOpen, Edit3, Loader2 } from 'lucide-react';
import {
  getLessonByTopic,
  lessonQueryKey,
  type SectionOutline,
  type Subject,
  type Topic,
} from '@/lib/api';
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
            <span className="ml-2 opacity-70">{subject.grade} класс</span>
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
  const [showArchive, setShowArchive] = useState(false);
  const [creatingIn, setCreatingIn] = useState<number | null>(null);
  const { data: sections, isLoading, error, refetch } = useTeacherOutline(subjectId, showArchive);

  if (isLoading) {
    return (
      <div className="py-12 flex justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4"><button type="button" onClick={() => setShowArchive(!showArchive)} className="rounded-lg border px-4 py-2 font-semibold">{showArchive ? 'Вернуться к программе' : 'Архив уроков'}</button>{showArchive && <p className="text-sm text-muted-foreground">Результаты учеников сохранены. Восстановленные уроки вернутся черновиками.</p>}</div>
      {!showArchive && <CreateSection subjectId={subjectId} />}
      {error && <p role="alert">Не удалось загрузить программу. <button onClick={() => refetch()}>Повторить</button></p>}
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
          {!showArchive && <div className="p-4"><button type="button" onClick={() => setCreatingIn(section.id)} className="rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground">Создать урок</button></div>}
          {creatingIn === section.id && <TopicForm section={section} onClose={() => setCreatingIn(null)} />}
          <TopicsList section={{ ...section, topics: section.topics.filter(topic => Boolean(topic.archived_at) === showArchive) }} />
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
  const archive = useArchiveTopic();
  const queryClient = useQueryClient();
  const prefetchLesson = () => {
    void queryClient.prefetchQuery({
      queryKey: lessonQueryKey(topic.id, 'teacher'),
      queryFn: () => getLessonByTopic(topic.id, 'teacher'),
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
    });
  };

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
              {topic.archived_at ? 'В архиве' : status.badgeText}
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
      <div className="flex flex-col gap-2">
      {!topic.archived_at && <Link
        href={`/dashboard/lessons/${topic.id}${topic.lesson_status === 'published' ? '?preview=1' : ''}`}
        onFocus={prefetchLesson}
        onMouseEnter={prefetchLesson}
        onTouchStart={prefetchLesson}
        className="flex items-center justify-center gap-2 px-5 py-2.5 bg-primary/10 text-primary font-bold rounded-xl hover:bg-primary hover:text-primary-foreground transition-all text-sm w-full md:w-auto"
      >
          <Edit3 className="w-4 h-4" />
          {topic.lesson_status === 'published' ? 'Посмотреть опубликованный урок' : topic.lesson_id ? 'Продолжить редактирование' : 'Создать материалы'}
      </Link>}
      <button type="button" disabled={archive.isPending} onClick={() => {
        if (!topic.archived_at && !window.confirm(`Убрать «${topic.name}» из программы? Результаты учеников сохранятся. Урок можно восстановить из архива.`)) return;
        archive.mutate({ topicId: topic.id, restore: Boolean(topic.archived_at) });
      }} className="rounded-lg border px-4 py-2 text-sm font-semibold disabled:opacity-50">{archive.isPending ? 'Сохраняется…' : topic.archived_at ? 'Восстановить черновиком' : 'Убрать из программы'}</button>
      {archive.error && <p role="alert" className="max-w-xs text-sm text-destructive">{archive.error.message}</p>}
      </div>
    </div>
  );
}
