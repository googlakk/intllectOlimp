import { useState, useRef, createContext, useContext } from 'react';
import { useSubjects, useUploadKtp, useLessonStatus, useSubjectTopics, useQuarters, currentQuarterNumber, getQuarterPlan, generateLesson, ApiError, type SubjectTopic,
  useClasses, useSubjectDeliveries, markDelivered, unmarkDelivered, type Delivery, type SchoolClass } from '@/lib/api';
import { Link } from 'wouter';
import { FileUp, BookOpen, Edit3, Loader2, Sparkles, Check, X } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';

export default function Lessons() {
  const { data: subjects, isLoading: loadingSubs } = useSubjects();
  const [selectedSubject, setSelectedSubject] = useState<number | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadMutation = useUploadKtp();
  const queryClient = useQueryClient();

  const handleUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setUploadError(null);
    setIsUploading(true);
    
    const reader = new FileReader();
    reader.onload = async (event) => {
      try {
        const text = event.target?.result as string;
        const json = JSON.parse(text);
        
        uploadMutation.mutate(json, {
          onSuccess: () => {
            setIsUploading(false);
            alert('КТП успешно загружен и обработан!');
            queryClient.invalidateQueries({ queryKey: ['subjects'] });
            queryClient.invalidateQueries({ queryKey: ['sections'] });
            queryClient.invalidateQueries({ queryKey: ['topics'] });
            queryClient.invalidateQueries({ queryKey: ['subject-topics'] });
            if (fileInputRef.current) fileInputRef.current.value = '';
          },
          onError: (err: any) => {
            setIsUploading(false);
            setUploadError(err.message || 'Ошибка загрузки КТП');
            if (fileInputRef.current) fileInputRef.current.value = '';
          }
        });
      } catch (err) {
        setIsUploading(false);
        setUploadError('Файл должен быть валидным JSON');
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };
    reader.onerror = () => {
      setIsUploading(false);
      setUploadError('Ошибка чтения файла');
      if (fileInputRef.current) fileInputRef.current.value = '';
    };
    reader.readAsText(file);
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Управление уроками</h1>
          <p className="text-muted-foreground mt-2 font-medium">Редактируйте материалы и структуру курсов</p>
          {uploadError && <p className="text-destructive text-sm mt-2 font-bold">{uploadError}</p>}
        </div>
        <input type="file" ref={fileInputRef} className="hidden" accept=".json" onChange={handleUpload} />
        <button 
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-bold rounded-xl shadow-md shadow-primary/20 hover:bg-primary/90 transition-all disabled:opacity-70"
        >
          {isUploading ? <Loader2 className="w-5 h-5 animate-spin" /> : <FileUp className="w-5 h-5" />}
          {isUploading ? 'Загрузка...' : 'Загрузить КТП (JSON)'}
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

      {selectedSubject && <SectionsList subjectId={selectedSubject} grade={subjects?.find((s) => s.id === selectedSubject)?.grade ?? 0} />}
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

const QUARTERS = [1, 2, 3, 4];

// Classes of the subject's parallel and the «Проведено» marks, shared by every topic row.
const DeliveryContext = createContext<{ subjectId: number; classes: SchoolClass[]; deliveries: Delivery[] }>({ subjectId: 0, classes: [], deliveries: [] });

function SectionsList({ subjectId, grade }: { subjectId: number; grade: number }) {
  const { data: topics, isLoading } = useSubjectTopics(subjectId);
  const { data: allClasses } = useClasses();
  const { data: deliveries } = useSubjectDeliveries(subjectId);
  const sameGrade = (allClasses ?? []).filter((c) => c.grade === grade);
  const deliveryContext = { subjectId, classes: sameGrade.length ? sameGrade : allClasses ?? [], deliveries: deliveries ?? [] };
  const { data: quarters } = useQuarters();
  const [quarter, setQuarter] = useState<number | null>(null);
  const activeQuarter = quarter ?? currentQuarterNumber(quarters);

  if (isLoading) return <div className="py-12 flex justify-center"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>;

  const inQuarter = (topics ?? []).filter((t) => (t.quarter ?? 0) === activeQuarter);
  const unassigned = (topics ?? []).filter((t) => !t.quarter);
  const ownerNumber = new Map((topics ?? []).map((t) => [t.id, t.sort_number]));
  const sections: Array<{ key: string; name: string; order: number; topics: SubjectTopic[] }> = [];
  for (const topic of inQuarter) {
    const last = sections[sections.length - 1];
    if (last && last.key === String(topic.section_id)) last.topics.push(topic);
    else sections.push({ key: String(topic.section_id), name: topic.section_name, order: topic.section_sort_order, topics: [topic] });
  }
  const dates = quarters?.find((q) => q.number === activeQuarter);

  return (
    <DeliveryContext.Provider value={deliveryContext}>
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex gap-2">
          {QUARTERS.map((n) => {
            const count = (topics ?? []).filter((t) => t.quarter === n).length;
            return (
              <button
                key={n}
                onClick={() => setQuarter(n)}
                className={`px-5 py-2.5 rounded-xl font-bold text-sm transition-all ${
                  activeQuarter === n ? 'bg-primary text-primary-foreground shadow-md' : 'bg-card border border-border text-muted-foreground hover:text-foreground'
                }`}
              >
                {n} четверть <span className="opacity-70 font-semibold">· {count}</span>
              </button>
            );
          })}
        </div>
        <GenerateQuarterButton subjectId={subjectId} quarter={activeQuarter} />
      </div>
      {dates && <p className="text-sm text-muted-foreground font-medium -mt-3">{dates.starts_on} — {dates.ends_on}</p>}

      {sections.map((section) => (
        <div key={section.key} className="bg-card rounded-[2rem] border border-border shadow-sm overflow-hidden">
          <div className="px-6 md:px-8 py-5 bg-muted/30 border-b border-border flex justify-between items-center">
            <h3 className="font-bold text-lg uppercase tracking-wide text-primary">Раздел {section.order}: {section.name}</h3>
            <span className="text-sm font-bold text-muted-foreground bg-card px-3 py-1 rounded-lg border border-border">
              {section.topics.reduce((sum, t) => sum + (t.hours || 0), 0)} ч в четверти
            </span>
          </div>
          <div className="divide-y divide-border/50">
            {section.topics.map((topic) =>
              topic.lesson_topic_id ? (
                <ContinuationRow key={topic.id} topic={topic} ownerNumber={ownerNumber.get(topic.lesson_topic_id) ?? null} />
              ) : (
                <TopicRow key={topic.id} topic={topic} />
              ),
            )}
          </div>
        </div>
      ))}
      {sections.length === 0 && (
        <div className="p-12 text-center text-sm font-medium text-muted-foreground bg-card rounded-[2rem] border border-dashed border-border">
          В этой четверти нет тем
        </div>
      )}
      {unassigned.length > 0 && (
        <p className="text-sm text-muted-foreground">Тем без четверти: {unassigned.length}. Они появятся во вкладках после повторной загрузки КТП.</p>
      )}
    </div>
    </DeliveryContext.Provider>
  );
}

const today = () => new Date().toISOString().slice(0, 10);
const shortDate = (iso: string) => iso.slice(8, 10) + '.' + iso.slice(5, 7);

// «Проведено»: one mark per class per date for this KTP row. Each mark opens the next lesson part for that class.
function DeliveredControl({ topicId }: { topicId: number }) {
  const { subjectId, classes, deliveries } = useContext(DeliveryContext);
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [classId, setClassId] = useState<number | ''>('');
  const [date, setDate] = useState(today());
  const [saving, setSaving] = useState(false);
  const marks = deliveries.filter((d) => d.topic_id === topicId);
  const className = (id: number) => classes.find((c) => c.id === id)?.name ?? `класс ${id}`;
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['deliveries', subjectId] });

  const save = async () => {
    const target = classId || classes[0]?.id;
    if (!target) return;
    setSaving(true);
    try {
      await markDelivered(topicId, target, date);
      refresh();
      setOpen(false);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Не удалось отметить');
    } finally {
      setSaving(false);
    }
  };

  const remove = async (mark: Delivery) => {
    if (!confirm(`Снять отметку «Проведено» для ${className(mark.class_id)} от ${shortDate(mark.conducted_on)}?`)) return;
    await unmarkDelivered(mark.id);
    refresh();
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {marks.map((mark) => (
        <span key={mark.id} className="inline-flex items-center gap-1 text-xs font-bold px-2 py-1 rounded-lg bg-green-500/10 text-green-700">
          <Check className="w-3 h-3" /> {className(mark.class_id)} · {shortDate(mark.conducted_on)}
          <button onClick={() => remove(mark)} className="ml-0.5 hover:text-destructive" title="Снять отметку"><X className="w-3 h-3" /></button>
        </span>
      ))}
      {classes.length === 0 ? (
        <span className="text-xs text-muted-foreground">Классы не созданы</span>
      ) : open ? (
        <span className="inline-flex items-center gap-2">
          <select className="rounded-lg border border-border bg-background px-2 py-1 text-xs" value={classId || classes[0].id} onChange={(e) => setClassId(Number(e.target.value))}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input type="date" className="rounded-lg border border-border bg-background px-2 py-1 text-xs" value={date} onChange={(e) => setDate(e.target.value)} />
          <button onClick={save} disabled={saving} className="text-xs font-bold px-3 py-1 rounded-lg bg-primary text-primary-foreground disabled:opacity-60">
            {saving ? '…' : 'Отметить'}
          </button>
          <button onClick={() => setOpen(false)} className="text-xs font-bold text-muted-foreground">Отмена</button>
        </span>
      ) : (
        <button onClick={() => setOpen(true)} className="text-xs font-bold px-3 py-1 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:border-primary/40">
          + Проведено
        </button>
      )}
    </div>
  );
}

function ContinuationRow({ topic, ownerNumber }: { topic: SubjectTopic; ownerNumber: number | null }) {
  return (
    <div className="px-6 md:px-8 py-4 flex items-center justify-between gap-4 bg-muted/5">
      <div className="flex items-center gap-3 text-muted-foreground">
        {topic.sort_number && <span className="text-xs font-mono font-bold bg-muted px-2 py-1 rounded">{topic.sort_number}</span>}
        <span className="font-semibold">{topic.name}</span>
        <span className="text-xs font-bold px-2 py-1 rounded bg-muted">продолжение темы №{ownerNumber ?? '—'} · {topic.hours} ч</span>
        <DeliveredControl topicId={topic.id} />
      </div>
      {topic.lesson_topic_id && (
        <Link href={`/dashboard/lessons/${topic.lesson_topic_id}`}>
          <span className="text-sm font-bold text-primary hover:underline cursor-pointer">К уроку темы</span>
        </Link>
      )}
    </div>
  );
}

function GenerateQuarterButton({ subjectId, quarter }: { subjectId: number; quarter: number }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<{ done: number; total: number; failed: number } | null>(null);
  const running = state !== null && state.done < state.total;

  const run = async () => {
    const plan = await getQuarterPlan(subjectId, quarter);
    const missing = plan.filter((item) => item.lesson_status === null);
    if (missing.length === 0) {
      alert('У всех тем этой четверти уже есть уроки');
      return;
    }
    if (!confirm(`Сгенерировать черновики для ${missing.length} тем без урока? Готовые уроки не изменятся.`)) return;
    let failed = 0;
    setState({ done: 0, total: missing.length, failed });
    // One at a time, in KTP order: each lesson's warm-up refers to the topics before it.
    for (let i = 0; i < missing.length; i++) {
      try {
        await generateLesson(missing[i].topic_id, true);
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 409)) failed += 1;
      }
      queryClient.invalidateQueries({ queryKey: ['lesson-status', missing[i].topic_id] });
      setState({ done: i + 1, total: missing.length, failed });
    }
  };

  return (
    <div className="flex items-center gap-3">
      {state && (
        <span className="text-sm font-semibold text-muted-foreground">
          {state.done}/{state.total}{state.failed ? ` · ошибок: ${state.failed}` : ''}
        </span>
      )}
      <button
        onClick={run}
        disabled={running}
        className="flex items-center gap-2 px-5 py-2.5 bg-primary/10 text-primary font-bold rounded-xl hover:bg-primary hover:text-primary-foreground transition-all text-sm disabled:opacity-60"
      >
        {running ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
        {running ? 'Генерация…' : `Сгенерировать ${quarter} четверть`}
      </button>
    </div>
  );
}

function TopicRow({ topic }: { topic: any }) {
  const { data: statusData, isLoading } = useLessonStatus(topic.id);
  
  let badgeClasses = "bg-muted text-muted-foreground";
  let badgeText = "Нет урока";
  
  if (!isLoading && statusData) {
    if (statusData.status === 'published') {
      badgeClasses = "bg-green-500/10 text-green-600";
      badgeText = "Опубликован";
    } else {
      badgeClasses = "bg-yellow-500/10 text-yellow-600";
      badgeText = "Черновик";
    }
  }

  return (
    <div className="p-6 md:px-8 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-muted/10 transition-colors">
      <div>
        <div className="flex items-center gap-3 mb-2">
          {(topic.sort_number ?? topic.ktp_number) && <span className="text-xs font-mono font-bold bg-muted px-2 py-1 rounded text-muted-foreground">{topic.sort_number ?? topic.ktp_number}</span>}
          <span className="font-bold text-foreground text-lg">{topic.name}</span>
          {!isLoading && (
            <span className={`text-xs font-bold px-2 py-1 rounded ${badgeClasses}`}>
              {badgeText}
            </span>
          )}
          {isLoading && <Loader2 className="w-3 h-3 animate-spin text-muted-foreground" />}
        </div>
        <div className="text-sm font-semibold text-muted-foreground flex items-center gap-4">
          <span className="bg-card border border-border px-2 py-0.5 rounded">{topic.hours} ч.</span>
          <span className="text-primary">{topic.lesson_type}</span>
        </div>
        <div className="mt-3"><DeliveredControl topicId={topic.id} /></div>
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
