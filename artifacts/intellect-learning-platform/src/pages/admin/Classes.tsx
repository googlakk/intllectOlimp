import { useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Loader2, Plus, RefreshCw, Trash2, Users } from 'lucide-react';
import {
  PROGRAM_LABEL, createClass, deleteClass, setStudentClass, syncBilimos, useClasses, useStudents,
  type SchoolClass,
} from '@/lib/api';

const input = 'rounded-xl border border-border bg-background px-3 py-2 text-sm';

function NewClassForm() {
  const queryClient = useQueryClient();
  const [system, setSystem] = useState<11 | 12>(11);
  const [grade, setGrade] = useState(7);
  const [letter, setLetter] = useState('');
  const [program, setProgram] = useState<SchoolClass['program']>('national');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!letter.trim()) return setError('Укажите букву класса');
    setSaving(true);
    setError(null);
    try {
      await createClass({ school_system: system, grade, letter: letter.trim(), program });
      setLetter('');
      queryClient.invalidateQueries({ queryKey: ['classes'] });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось создать класс');
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={submit} className="bg-card rounded-2xl border border-border p-5 flex flex-wrap items-end gap-3">
      <label className="text-sm font-semibold text-muted-foreground flex flex-col gap-1">
        Система
        <select className={input} value={system} onChange={(e) => setSystem(Number(e.target.value) as 11 | 12)}>
          <option value={11}>11-летка</option>
          <option value={12}>12-летка</option>
        </select>
      </label>
      <label className="text-sm font-semibold text-muted-foreground flex flex-col gap-1">
        Параллель
        <select className={input} value={grade} onChange={(e) => setGrade(Number(e.target.value))}>
          {Array.from({ length: 12 }, (_, i) => i + 1).map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
      </label>
      <label className="text-sm font-semibold text-muted-foreground flex flex-col gap-1">
        Буква
        <input className={`${input} w-20`} maxLength={5} placeholder="Б" value={letter} onChange={(e) => setLetter(e.target.value)} />
      </label>
      <label className="text-sm font-semibold text-muted-foreground flex flex-col gap-1">
        Программа
        <select className={input} value={program} onChange={(e) => setProgram(e.target.value as SchoolClass['program'])}>
          <option value="national">Национальная</option>
          <option value="cambridge">Cambridge</option>
        </select>
      </label>
      <button disabled={saving} className="px-5 py-2.5 bg-primary text-primary-foreground font-bold rounded-xl text-sm flex items-center gap-2 disabled:opacity-60">
        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Добавить класс
      </button>
      {error && <p className="w-full text-sm font-bold text-destructive">{error}</p>}
    </form>
  );
}

export default function Classes() {
  const queryClient = useQueryClient();
  const { data: classes, isLoading } = useClasses();
  const { data: students, isLoading: loadingStudents } = useStudents();
  const [filter, setFilter] = useState<'all' | 'none' | number>('none');
  const [search, setSearch] = useState('');
  const [busy, setBusy] = useState<number | null>(null);
  const [syncing, setSyncing] = useState(false);

  const refreshFromBilimos = async () => {
    setSyncing(true);
    try {
      await syncBilimos();
      queryClient.invalidateQueries({ queryKey: ['classes'] });
      queryClient.invalidateQueries({ queryKey: ['students'] });
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Не удалось обновить из BilimOs');
    } finally {
      setSyncing(false);
    }
  };

  const classById = useMemo(() => new Map((classes ?? []).map((c) => [c.id, c])), [classes]);
  const shown = (students ?? []).filter((s) =>
    (filter === 'all' || (filter === 'none' ? s.class_id === null : s.class_id === filter)) &&
    s.name.toLowerCase().includes(search.trim().toLowerCase()),
  );

  const assign = async (studentId: number, classId: number | null) => {
    setBusy(studentId);
    try {
      await setStudentClass(studentId, classId);
      queryClient.invalidateQueries({ queryKey: ['students'] });
      queryClient.invalidateQueries({ queryKey: ['classes'] });
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Не удалось сохранить');
    } finally {
      setBusy(null);
    }
  };

  const remove = async (row: SchoolClass) => {
    if (!confirm(`Удалить класс ${row.name}? Ученики останутся, но без класса.`)) return;
    await deleteClass(row.id);
    queryClient.invalidateQueries({ queryKey: ['classes'] });
    queryClient.invalidateQueries({ queryKey: ['students'] });
    if (filter === row.id) setFilter('none');
  };

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Классы</h1>
          <button onClick={refreshFromBilimos} disabled={syncing} className="px-4 py-2 border border-border bg-card font-bold rounded-xl text-sm flex items-center gap-2 disabled:opacity-60">
            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} /> Обновить из BilimOs
          </button>
        </div>
        <p className="text-muted-foreground mt-2 font-medium">
          Класс = система + параллель + буква + программа. По классу ученик получает свои КТП, а шаги тем открываются по отметке «Проведено».
        </p>
      </div>

      <NewClassForm />

      {isLoading ? <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /> : (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {(classes ?? []).map((c) => (
            <div
              key={c.id}
              onClick={() => setFilter(c.id)}
              className={`cursor-pointer rounded-2xl border p-4 transition-all ${filter === c.id ? 'border-primary bg-primary/5' : 'border-border bg-card hover:border-primary/40'}`}
            >
              <div className="flex items-start justify-between">
                <span className="text-2xl font-extrabold text-foreground">{c.name}</span>
                {c.source === 'bilimos' ? (
                  <span className="text-[10px] font-bold uppercase text-muted-foreground" title="Меняется только в BilimOs">BilimOs</span>
                ) : (
                  <button onClick={(e) => { e.stopPropagation(); remove(c); }} className="text-muted-foreground hover:text-destructive" title="Удалить класс">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
              <div className="text-xs font-semibold text-muted-foreground mt-1">{c.school_system}-летка · {PROGRAM_LABEL[c.program]}</div>
              <div className="text-sm font-bold text-foreground mt-2 flex items-center gap-1.5"><Users className="w-4 h-4" /> {c.student_count}</div>
            </div>
          ))}
          {classes?.length === 0 && <p className="text-sm text-muted-foreground col-span-full">Классов пока нет — добавьте первый.</p>}
        </div>
      )}

      <div className="bg-card rounded-[2rem] border border-border overflow-hidden">
        <div className="px-6 py-4 border-b border-border flex flex-wrap items-center gap-3 bg-muted/30">
          <h3 className="font-bold text-foreground mr-auto">Ученики</h3>
          <input className={input} placeholder="Поиск по имени" value={search} onChange={(e) => setSearch(e.target.value)} />
          <select
            className={input}
            value={String(filter)}
            onChange={(e) => setFilter(e.target.value === 'all' || e.target.value === 'none' ? e.target.value : Number(e.target.value))}
          >
            <option value="none">Без класса</option>
            <option value="all">Все</option>
            {(classes ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        {loadingStudents ? (
          <div className="p-8 flex justify-center"><Loader2 className="w-6 h-6 animate-spin text-muted-foreground" /></div>
        ) : (
          <div className="divide-y divide-border/50">
            {shown.map((s) => {
              const current = s.class_id !== null ? classById.get(s.class_id) : undefined;
              // Offer the student's own parallel first; any class can still be chosen.
              const options = [...(classes ?? [])].sort((a, b) => Number(b.grade === s.grade) - Number(a.grade === s.grade) || a.grade - b.grade);
              return (
                <div key={s.id} className="px-6 py-3 flex items-center justify-between gap-4">
                  <div>
                    <div className="font-semibold text-foreground">{s.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {current ? `${current.name} · ${current.school_system}-летка · ${PROGRAM_LABEL[current.program]}` : `${s.grade} класс, буква не назначена`}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {busy === s.id && <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />}
                    <select
                      className={input}
                      value={s.class_id ?? ''}
                      disabled={busy === s.id || s.source === 'bilimos'}
                      title={s.source === 'bilimos' ? 'Класс ученика задаётся в BilimOs' : undefined}
                      onChange={(e) => assign(s.id, e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">— без класса —</option>
                      {options.map((c) => <option key={c.id} value={c.id}>{c.name} · {PROGRAM_LABEL[c.program]}</option>)}
                    </select>
                  </div>
                </div>
              );
            })}
            {shown.length === 0 && <div className="p-8 text-center text-sm text-muted-foreground">Нет учеников</div>}
          </div>
        )}
      </div>
    </div>
  );
}
