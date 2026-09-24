import { useState } from 'react';
import { useLocation } from 'wouter';
import { useSaveTopic, type SectionOutline, type Topic } from '@/lib/api';
import { LESSON_TYPE_LABELS } from './listModel';

export function defaultCoveredTopics(section: SectionOutline, topic?: Topic) {
  const index = topic ? section.topics.findIndex(item => item.id === topic.id) : section.topics.length;
  return section.topics.slice(0, index < 0 ? section.topics.length : index)
    .filter(item => !item.archived_at && ['study', 'project'].includes(item.lesson_type)).map(item => item.id);
}

export function defaultSourceAssessment(section: SectionOutline, topic?: Topic): string {
  if (topic) return String(topic.source_assessment_topic_id ?? '');
  return String([...section.topics].reverse().find(item => !item.archived_at && item.lesson_type === 'assessment')?.id ?? '');
}

export default function TopicForm({ section, topic, onClose }: { section: SectionOutline; topic?: Topic; onClose: () => void }) {
  const [, navigate] = useLocation();
  const save = useSaveTopic();
  const [name, setName] = useState(topic?.name ?? '');
  const [kind, setKind] = useState(topic?.lesson_type ?? 'study');
  const [objectives, setObjectives] = useState(topic?.learning_objectives ?? '');
  const [covered, setCovered] = useState(topic?.covered_topic_ids ?? defaultCoveredTopics(section, topic));
  const [source, setSource] = useState(defaultSourceAssessment(section, topic));
  const special = ['review', 'assessment', 'reflection'].includes(kind);
  const currentIndex = topic ? section.topics.findIndex(item => item.id === topic.id) : section.topics.length;
  const candidates = section.topics.slice(0, currentIndex < 0 ? section.topics.length : currentIndex).filter(item => !item.archived_at);
  const field = 'mt-1 w-full rounded-lg border border-border bg-background p-3 text-sm';
  return <form className="space-y-4 rounded-xl border border-border bg-card p-5" onSubmit={async event => {
    event.preventDefault();
    try {
      const result = await save.mutateAsync({ sectionId: section.id, topicId: topic?.id, data: {
        name: name.trim(), lesson_type: kind, learning_objectives: objectives.trim(),
        covered_topic_ids: special ? covered : [], source_assessment_topic_id: kind === 'reflection' && source ? Number(source) : null,
      } });
      onClose();
      if (!topic) navigate(`/dashboard/lessons/${result.id}`);
    } catch { /* Keep the form intact so the teacher can retry. */ }
  }}>
    <h3 className="font-bold">{topic ? 'Тема и цели урока' : '1. Выберите тему урока'}</h3>
    <p className="text-sm text-muted-foreground">Раздел: {section.name}</p>
    <label className="block text-sm font-semibold">Название<input required autoFocus maxLength={300} value={name} onChange={event => setName(event.target.value)} className={field} /></label>
    <label className="block text-sm font-semibold">Тип занятия<select value={kind} onChange={event => {
      setKind(event.target.value);
      if (!topic && event.target.value === 'reflection' && source) {
        const assessment = section.topics.find(item => item.id === Number(source));
        setCovered(assessment?.covered_topic_ids ?? []);
      }
    }} className={field}>{Object.entries(LESSON_TYPE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
    {special && <fieldset className="space-y-2"><legend className="mb-2 text-sm font-semibold">Какие темы проверяем или повторяем</legend>
      {candidates.length === 0 && <p className="text-sm text-muted-foreground">Добавьте предметные темы в раздел, затем выберите их здесь.</p>}
      {candidates.map(item => <label key={item.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={covered.includes(item.id)} onChange={event => setCovered(event.target.checked ? [...covered, item.id] : covered.filter(id => id !== item.id))} />{item.name}</label>)}
    </fieldset>}
    {kind === 'reflection' && <label className="block text-sm font-semibold">Связанная контрольная<select className={field} value={source} onChange={event => {
      setSource(event.target.value);
      if (event.target.value) setCovered(section.topics.find(item => item.id === Number(event.target.value))?.covered_topic_ids ?? []);
    }}><option value="">Общий разбор</option>{source && !candidates.some(item => item.id === Number(source)) && <option value={source}>Прежняя контрольная (в архиве)</option>}{candidates.filter(item => item.lesson_type === 'assessment').map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
    <label className="block text-sm font-semibold">Что ученик научится делать<textarea rows={3} value={objectives} onChange={event => setObjectives(event.target.value)} placeholder="Например: сравнивать дроби; вычислять квадратный корень" className={field} /></label>
    <p className="text-xs text-muted-foreground">Если оставить цели пустыми, платформа предложит их по теме. Их можно уточнить перед подготовкой материалов.</p>
    {save.error && <p role="alert" className="text-sm text-destructive">Не удалось сохранить: {save.error.message}</p>}
    <div className="flex flex-wrap gap-3"><button disabled={save.isPending || !name.trim()} className="rounded-lg bg-primary px-4 py-2 font-semibold text-primary-foreground disabled:opacity-50">{save.isPending ? 'Сохраняется…' : topic ? 'Сохранить' : 'Создать и перейти к материалам'}</button><button type="button" onClick={onClose} className="rounded-lg border px-4 py-2">Отмена</button></div>
  </form>;
}
