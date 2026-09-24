import { useEffect, useRef, useState } from 'react';
import { Link } from 'wouter';
import { ArrowLeft, ArrowRight, RotateCcw, Sparkles } from 'lucide-react';
import { useAuth } from '@/components/auth/AuthContext';
import { PhysicsScenes } from './PhysicsScenes';
import { HistoryScenes } from './HistoryScenes';
import { physicsLesson } from './physicsContent';
import { historyLesson } from './historyContent';
import { answerSample, emptySample, restoreSample, type SampleLessonData } from './sampleModel';
import './samples.css';

function Experience({ lesson, identity, home }: { lesson: SampleLessonData; identity: string; home: string }) {
  const key = `intellect:visual:${lesson.id}:v1:${identity}`;
  const [state, setState] = useState(() => { try { return restoreSample(localStorage.getItem(key), lesson); } catch { return emptySample(); } });
  const [saved, setSaved] = useState(true);
  const [restart, setRestart] = useState(false);
  const [saveNonce, setSaveNonce] = useState(0);
  const main = useRef<HTMLElement>(null);
  useEffect(() => { try { localStorage.setItem(key, JSON.stringify(state)); setSaved(true); } catch { setSaved(false); } }, [key, state, saveNonce]);
  useEffect(() => { main.current?.focus({ preventScroll: true }); window.scrollTo({ top: 0, behavior: 'instant' }); }, [state.step]);
  useEffect(() => { const previous = document.title; document.title = `${lesson.title} · Интеллект`; return () => { document.title = previous; }; }, [lesson.title]);
  const go = (step: number) => setState(current => ({ ...current, step }));
  const Scenes = lesson.id === 'density' ? PhysicsScenes : HistoryScenes;
  return <div className={`sample-app sample-${lesson.id}`}>
    <header className="sample-header"><Link href={home}><ArrowLeft size={17} />В кабинет</Link><Link href="/visual/square-roots" className="sample-brand"><Sparkles size={20} /><strong>intellect</strong><span>живая {lesson.id === 'density' ? 'физика' : 'история'}</span></Link><button type="button" className="sample-icon-button" aria-label="Начать урок заново" aria-expanded={restart} onClick={() => setRestart(!restart)}><RotateCcw size={18} /></button></header>
    {restart && <div className="sample-reset"><p>Начать заново? Сохранённые ответы этого образца на устройстве будут сброшены.</p><button onClick={() => { setState(emptySample()); setRestart(false); }}>Начать заново</button><button onClick={() => setRestart(false)}>Отмена</button></div>}
    <nav className="sample-progress" aria-label="Сцены урока">{lesson.sceneNames.map((name, i) => <button key={name} type="button" aria-label={`Сцена ${i + 1}: ${name}`} aria-current={state.step === i ? 'step' : undefined} onClick={() => go(i)}><span>{String(i + 1).padStart(2, '0')}</span><span>{name}</span></button>)}</nav>
    <main tabIndex={-1} ref={main} className="sample-main" aria-label={lesson.sceneNames[state.step]}><div className="sample-scene" key={state.step}><Scenes step={state.step} answers={state.answers} onAnswer={(id, choice) => setState(current => answerSample(current, lesson, id, choice))} /></div></main>
    <footer className="sample-footer"><div><p role="status">{saved ? '● Место и ответы сохранены на устройстве' : 'Не удалось сохранить. Не закрывай вкладку.'}</p>{!saved && <button onClick={() => setSaveNonce(n => n + 1)}>Повторить сохранение</button>}<small>Образец · 7 класс · отдельно от оценок курса</small></div><div className="sample-footer-controls">{state.step > 0 && <button className="sample-icon-button" aria-label="Предыдущая сцена" onClick={() => go(state.step - 1)}><ArrowLeft size={19} /></button>}<span>{state.step + 1} / {lesson.sceneNames.length}</span>{state.step < lesson.sceneNames.length - 1 ? <button className="sample-primary" onClick={() => go(state.step + 1)}>{state.step === 0 ? 'Начать исследование' : state.step === lesson.sceneNames.length - 2 ? 'Мои открытия' : 'Дальше'}<ArrowRight size={18} /></button> : <Link className="sample-primary" href={lesson.id === 'density' ? '/visual/silk-road' : '/visual/density'}>Открыть {lesson.id === 'density' ? 'историю' : 'физику'}<ArrowRight size={18} /></Link>}</div></footer>
  </div>;
}

export default function SampleLesson({ kind }: { kind: 'density' | 'silk-road' }) {
  const { user, isLoading } = useAuth();
  if (isLoading) return <div className="sample-loading">Открываем урок…</div>;
  const lesson = kind === 'density' ? physicsLesson : historyLesson;
  const home = user ? user.role === 'student' ? '/learn' : '/dashboard/lessons' : '/';
  return <Experience key={`${kind}:${user?.id ?? 'guest'}`} lesson={lesson} identity={String(user?.id ?? 'guest')} home={home} />;
}
