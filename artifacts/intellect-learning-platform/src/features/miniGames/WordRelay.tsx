import { useState } from 'react';
import { Eye, EyeOff, Mic2, Check, SkipForward } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { GameError, GameFrame, GameResult, RoundClock, TeamCount } from './GameFrame';
import { readGame, TEAM_NAMES, type GameData, type GameProps } from './model';

export default function WordRelay(props: GameProps) {
  const [session, setSession] = useState(0); const data = readGame('WordRelay', props);
  return data ? <Relay key={`${session}:${JSON.stringify(data)}`} data={data} reset={() => setSession(n => n + 1)} /> : <GameError />;
}
function Relay({ data, reset }: { data: GameData['WordRelay']; reset: () => void }) {
  const [teams, setTeams] = useState(2), [phase, setPhase] = useState<'setup' | 'ready' | 'peek' | 'play' | 'review'>('setup');
  const [round, setRound] = useState(0), [scores, setScores] = useState<number[]>(Array(6).fill(0)), [guessed, setGuessed] = useState(false);
  const [timeUp, setTimeUp] = useState(false);
  const done = round === data.cards.length, card = data.cards[round], team = round % teams;
  const review = (success: boolean) => {
    if (phase !== 'play') return;
    if (success) setScores(old => old.map((n, i) => n + Number(i === team)));
    setGuessed(success); setPhase('review');
  };
  return <GameFrame game={data} theme="words" name="Объясни без запретных слов" onReset={reset}>
    {done ? <GameResult headline="Слова найдены. Смысл понятен." takeaway={data.takeaway}><div className="mg-teams">{TEAM_NAMES.slice(0, teams).map((name, i) => { const turns = data.cards.filter((_, n) => n % teams === i).length; return <div key={name} className="mg-team">{name}<strong>{scores[i]} / {turns}</strong><small>Слов угадано</small></div>; })}</div></GameResult> : <>
      <div className="mg-word-stage">
        {phase === 'peek' || phase === 'review' ? <><span className="mg-eyebrow" style={{ color: '#ffe7bd' }}>{phase === 'peek' ? 'ВИДИТ ТОЛЬКО ОБЪЯСНЯЮЩИЙ' : guessed ? 'СЛОВО УГАДАНО' : 'СЛОВО ДЛЯ РАЗБОРА'}</span><h4>{card.term}</h4>{phase === 'peek' && <><p className="mb-2 text-xs uppercase tracking-wider">Нельзя произносить и использовать однокоренные</p><div className="mg-forbidden">{card.forbidden.map(word => <span key={word}>{word}</span>)}</div><button className="mg-button mt-5" onClick={() => { setPhase('play'); setTimeUp(false); }}><EyeOff size={17} /> Запомнил — скрыть</button></>}</> : <><Mic2 size={42} strokeWidth={1.4} /><div className="mg-wave" aria-hidden="true">{Array.from({ length: 9 }, (_, i) => <i key={i} />)}</div><h4>{phase === 'play' ? 'Теперь своими словами' : 'Мысль громче слова'}</h4>{phase === 'ready' && <button className="mg-button" onClick={() => setPhase('peek')}><Eye size={17} /> Показать слово объясняющему</button>}</>}
      </div>
      {phase === 'setup' ? <><p className="mg-question">Объясни понятие. Обойди очевидное.</p><p className="mg-muted">Команда отворачивается от экрана. Объясняющий запоминает слово и запреты, затем скрывает карточку. Можно говорить, рисовать или показывать жестами. Каждый раунд — новый объясняющий.</p><div className="mg-actions"><TeamCount value={teams} onChange={setTeams} /><button className="mg-button" onClick={() => setPhase('ready')}>Включить студию</button></div></> : <>
        <div className="mg-round-label"><span>{TEAM_NAMES[team]} · СЛОВО {round + 1} / {data.cards.length}</span>{phase === 'play' && <RoundClock key={round} seconds={30} onEnd={() => setTimeUp(true)} />}</div>
        {phase === 'ready' && <p className="mg-muted">Новый объясняющий у экрана. Остальная команда отворачивается, пока слово не будет скрыто.</p>}
        {phase === 'play' && <>{timeUp && <p role="status" className="mg-feedback">30 секунд прошло. Завершите ответ или добавьте время кнопкой таймера.</p>}<p className="mg-muted">Учитель запускает таймер и отмечает результат. Само слово на экране скрыто.</p><div className="mg-actions"><button className="mg-button" onClick={() => review(true)}><Check size={17} /> Угадали без нарушений</button><button className="mg-button secondary" onClick={() => review(false)}><SkipForward size={17} /> Разобрать и пропустить</button></div></>}
        {phase === 'review' && <><div className="mg-feedback"><RichText text={card.hint} /></div><button className="mg-button mt-4" onClick={() => { setRound(n => n + 1); setPhase('ready'); }}>{round === data.cards.length - 1 ? 'Итоги студии' : 'Передать микрофон →'}</button></>}
      </>}
    </>}
  </GameFrame>;
}
