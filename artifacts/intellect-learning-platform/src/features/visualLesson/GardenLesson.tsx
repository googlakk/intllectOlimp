import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, Leaf, RotateCcw } from 'lucide-react';
import { Link } from 'wouter';
import { useAuth } from '@/components/auth/AuthContext';
import { GardenScenes } from './GardenScenes';
import { initialState, recordAnswer, restoreState, sceneNames, type QuestionId } from './model';
import './garden.css';

function GardenExperience({ identity, home }: { identity: string; home: string }) {
  const storageKey = `intellect:square-garden:v1:${identity}`;
  const [state, setState] = useState(() => { try { return restoreState(localStorage.getItem(storageKey)); } catch { return initialState(); } });
  const [saved, setSaved] = useState(true);
  const [reset, setReset] = useState(false);
  const content = useRef<HTMLElement>(null);
  useEffect(() => { try { localStorage.setItem(storageKey, JSON.stringify(state)); setSaved(true); } catch { setSaved(false); } }, [state, storageKey]);
  useEffect(() => { content.current?.focus({ preventScroll: true }); window.scrollTo({ top: 0, behavior: 'instant' }); }, [state.step]);
  const go = (step: number) => setState(current => ({ ...current, step }));
  const question: QuestionId | null = state.step === 4 ? 'predict' : state.step === 5 ? 'trap' : state.step === 6 ? 'project' : null;
  const ready = state.step === 1 ? state.side === 4 : question ? state.responses[question]?.correct : true;
  return <div className="garden-app">
    <header className="garden-header"><Link href={home} className="garden-exit"><ArrowLeft size={18} /><span>В кабинет</span></Link><div className="garden-brand"><Leaf size={22} /><strong>intellect<span> / живая математика</span></strong></div><button className="garden-reset" onClick={() => setReset(!reset)} aria-expanded={reset} aria-label="Начать урок заново"><RotateCcw size={18} /></button></header>
    {reset && <div className="garden-reset-confirm"><p>Начать заново? Ответы и место остановки этого образца на устройстве будут сброшены.</p><button onClick={() => { setState(initialState()); setReset(false); }}>Начать заново</button><button onClick={() => setReset(false)}>Отмена</button></div>}
    <nav className="garden-progress" aria-label="Сцены урока">{sceneNames.map((name, i) => <button key={name} aria-label={`Сцена ${i + 1}: ${name}`} aria-current={state.step === i ? 'step' : undefined} onClick={() => go(i)}><span>{String(i + 1).padStart(2, '0')}</span><span>{name}</span></button>)}</nav>
    <main ref={content} tabIndex={-1} className="garden-main" aria-label={sceneNames[state.step]}><div key={state.step} className="garden-scene-enter"><GardenScenes state={state} setSide={side => setState(current => ({ ...current, side }))} answer={(id, value) => setState(current => recordAnswer(current, id, value))} go={go} /></div></main>
    <footer className="garden-footer"><div><span className="garden-save-dot" data-saved={saved} /><span role="status">{saved ? 'Место сохранено на этом устройстве' : 'Не удалось сохранить. Урок можно продолжить, но не закрывай вкладку.'}</span><small>Образец урока · вне оценок курса</small></div><div className="garden-footer-controls">{state.step > 0 && <button className="garden-back" onClick={() => go(state.step - 1)} aria-label="Предыдущая сцена"><ArrowLeft size={20} /></button>}<span>{state.step + 1} / {sceneNames.length}</span>{state.step < 7 ? <><button className="garden-primary" disabled={!ready} onClick={() => go(state.step + 1)}>{state.step === 0 ? 'Начать' : state.step === 6 ? 'Мои открытия' : 'Дальше'}<ArrowRight size={18} /></button>{!ready && <button className="garden-skip" onClick={() => go(state.step + 1)}>Пока пропустить</button>}</> : <Link className="garden-primary" href={home}>В кабинет <ArrowRight size={18} /></Link>}</div></footer>
  </div>;
}

export default function GardenLesson() {
  const { user, isLoading } = useAuth();
  if (isLoading) return <div className="garden-app garden-loading">Открываем мастерскую…</div>;
  return <GardenExperience key={user?.id ?? 'guest'} identity={String(user?.id ?? 'guest')} home={user ? user.role === 'student' ? '/learn' : '/dashboard/lessons' : '/'} />;
}
