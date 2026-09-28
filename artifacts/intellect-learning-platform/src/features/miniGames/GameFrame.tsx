import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { Clock3, HelpCircle, Pause, Play, RotateCcw, Sparkles, Users, UserRound } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import type { GameBase } from './model';
import './miniGames.css';

export function GameFrame({ game, theme, name, group = true, children, onReset }: { game: GameBase; theme: string; name: string; group?: boolean; children: ReactNode; onReset: () => void }) {
  const id = useId();
  const [help, setHelp] = useState(false);
  const [reset, setReset] = useState(false);
  return <section className={`mini-game mg-${theme}`} aria-labelledby={id}>
    <header className="mg-header">
      <div className="mg-eyebrow"><Sparkles size={14} /> МИНИ-ИГРА <span className="mg-rule" /> {name}</div>
      <div className="mg-heading"><h3 id={id}>{game.title}</h3><button className="mg-icon" aria-label="Правила мини-игры" aria-expanded={help} onClick={() => setHelp(!help)}><HelpCircle size={20} /></button></div>
      <div className="mg-meta"><span>{group ? <Users size={14} /> : <UserRound size={14} />}{group ? 'Вместе в классе' : 'Каждый сам'}</span><span><Clock3 size={14} />{game.duration_minutes} минут</span></div>
      <RichText text={game.instruction} className="mg-muted mt-3" />
      {help && <div className="mg-help"><RichText text={game.instruction} /><p>{group ? 'Один экран для класса. Учитель ведёт игру, ученики обсуждают ответы. Результаты команд остаются только на этом экране.' : 'Решай самостоятельно. Можно попробовать ещё раз после объяснения.'}</p></div>}
    </header>
    <div className="mg-body">{children}</div>
    <footer className="mg-footer"><span>{group ? 'Обсуждаем → объясняем → играем' : 'Думай в своём темпе'}</span><button className="mg-reset" onClick={() => setReset(true)}><RotateCcw size={14} /> Заново</button></footer>
    {reset && <div className="mg-reset-confirm" role="group" aria-label="Подтверждение сброса"><p>Начать эту мини-игру заново? Текущий результат сбросится.</p><button className="mg-button" onClick={onReset}>Начать заново</button><button className="mg-button secondary" onClick={() => setReset(false)}>Продолжить игру</button></div>}
  </section>;
}

export function GameResult({ headline, takeaway, children }: { headline: string; takeaway: string; children?: ReactNode }) {
  return <div className="mg-result" role="status"><div className="mg-result-star" aria-hidden="true">✦</div><span className="mg-eyebrow">МИССИЯ ЗАВЕРШЕНА</span><h4>{headline}</h4>{children}<div className="mg-takeaway"><span>Забираем в урок</span><RichText text={takeaway} /></div><p className="mg-muted">Обсудите вывод и переходите к следующему блоку урока.</p></div>;
}

export function GameError() { return <p role="alert" className="rounded-xl border p-5">В данных мини-игры есть ошибка. Учителю нужно проверить задания в редакторе.</p>; }

export function TeamCount({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return <label className="mg-team-count">Команд <select value={value} onChange={e => onChange(Number(e.target.value))}>{[2, 3, 4, 5, 6].map(n => <option key={n}>{n}</option>)}</select></label>;
}

/** Starts only on an explicit click; absolute deadlines survive background tabs. */
export function RoundClock({ seconds = 30, onEnd }: { seconds?: number; onEnd?: () => void }) {
  const [left, setLeft] = useState(seconds);
  const [running, setRunning] = useState(false);
  const deadline = useRef(0);
  const end = useRef(onEnd);
  end.current = onEnd;
  useEffect(() => {
    if (!running) return;
    const update = () => {
      const next = Math.max(0, Math.ceil((deadline.current - Date.now()) / 1000));
      setLeft(next);
      if (next === 0) { setRunning(false); end.current?.(); }
    };
    const interval = window.setInterval(update, 200);
    return () => window.clearInterval(interval);
  }, [running]);
  return <div className="mg-clock"><span role="timer" aria-label={`Осталось ${left} секунд`}>{Math.floor(left / 60)}:{String(left % 60).padStart(2, '0')}</span><button className="mg-icon" aria-label={running ? 'Пауза таймера' : left ? 'Запустить таймер' : 'Ещё время'} onClick={() => { if (running) { setRunning(false); } else { const duration = left || seconds; setLeft(duration); deadline.current = Date.now() + duration * 1000; setRunning(true); } }}>{running ? <Pause size={18} /> : <Play size={18} />}</button></div>;
}

export function ChoiceButtons({ options, selected, onSelect, disabled = false }: { options: string[]; selected: number | null; onSelect: (i: number) => void; disabled?: boolean }) {
  return <div className="mg-options">{options.map((option, i) => <button key={i} type="button" aria-pressed={selected === i} disabled={disabled} className={`mg-option ${selected === i ? 'selected' : ''}`} onClick={() => onSelect(i)}><span className="mg-option-letter">{String.fromCharCode(65 + i)}</span><RichText text={option} /></button>)}</div>;
}
