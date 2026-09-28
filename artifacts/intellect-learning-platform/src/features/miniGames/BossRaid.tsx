import { useState } from 'react';
import { Shield, Swords, Check } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { GameError, GameFrame, GameResult, RoundClock, TeamCount } from './GameFrame';
import { readGame, TEAM_NAMES, type GameData, type GameProps } from './model';

export default function BossRaid(props: GameProps) {
  const [session, setSession] = useState(0);
  const data = readGame('BossRaid', props);
  return data ? <Raid key={`${session}:${JSON.stringify(data)}`} data={data} reset={() => setSession(n => n + 1)} /> : <GameError />;
}

function Raid({ data, reset }: { data: GameData['BossRaid']; reset: () => void }) {
  const [teams, setTeams] = useState(3), [started, setStarted] = useState(false);
  const [round, setRound] = useState(0), [revealed, setRevealed] = useState(false);
  const [chosen, setChosen] = useState<number[]>([]), [scores, setScores] = useState<number[]>(Array(6).fill(0));
  const [hits, setHits] = useState(0);
  const done = round === data.rounds.length;
  const item = data.rounds[round];
  function strike() {
    if (!revealed || done) return;
    setScores(current => current.map((n, i) => n + Number(chosen.includes(i))));
    setHits(n => n + Number(chosen.length > 0));
    setRound(n => n + 1); setChosen([]); setRevealed(false);
  }
  return <GameFrame game={data} theme="boss" name="Одолей босса" onReset={reset}>
    <div className="mg-boss-scene" aria-label={`Снято щитов: ${hits} из ${data.rounds.length}`}>
      <span className="mg-orbit-tag">ОРБИТАЛЬНАЯ МИССИЯ / 01</span>
      <svg className="mg-boss-svg" viewBox="0 0 180 190" aria-hidden="true"><path d="M35 52 22 15 66 36 115 36 158 15 144 52 163 99 140 150 91 176 42 151 16 101Z" fill="#8880e5" stroke="#c9c7ff" strokeWidth="3" /><path d="m35 52 55 24 54-24-6 75-48 26-48-26Z" fill="#393873"/><path d="m47 76 30 12-3 17-26-9ZM133 76l-30 12 3 17 26-9Z" fill="#cdf88c"/><path d="m72 125 18-10 18 10-18 8Z" fill="#c9c7ff"/><path d="m43 150 47 26 49-26-18-13-31 16-31-16Z" fill="#5a53a5"/><circle cx="91" cy="44" r="7" fill="#cdf88c"/></svg>
      <div className="mg-shields">{data.rounds.map((_, i) => <span key={i} className={`mg-shield ${i < hits ? 'broken' : ''}`} />)}</div>
    </div>
    {done ? <GameResult headline={hits === data.rounds.length ? 'Босс побеждён. Вместе!' : 'Есть над чем потренироваться'} takeaway={data.takeaway}><p>{hits} из {data.rounds.length} щитов снято</p><div className="mg-teams">{scores.slice(0, teams).map((score, i) => <div className="mg-team" key={i}>{TEAM_NAMES[i]}<strong>{score} ✦</strong></div>)}</div></GameResult> : !started ? <><p className="mg-question">Каждый верный ответ — удар по щиту.</p><p className="mg-muted">Все команды обсуждают одно задание одновременно. Учитель открывает ответ и отмечает команды, которые объяснили решение.</p><div className="mg-actions"><TeamCount value={teams} onChange={setTeams} /><button className="mg-button" onClick={() => setStarted(true)}><Swords size={18} /> Начать атаку</button></div></> : <>
      <div className="mg-round-label"><span>ЩИТ {round + 1} / {data.rounds.length}</span><RoundClock key={round} seconds={45} /></div>
      <div className="mg-panel"><RichText className="mg-question" text={item.question} />{!revealed ? <button className="mg-button" onClick={() => setRevealed(true)}>Открыть ответ</button> : <><div className="mg-feedback"><strong>Ответ для обсуждения</strong><RichText text={item.answer} /><RichText text={item.explanation} /></div><p className="mg-muted mt-4">Кто дал верный ответ и объяснил его?</p><div className="mg-teams">{TEAM_NAMES.slice(0, teams).map((name, i) => <button aria-pressed={chosen.includes(i)} key={name} className={`mg-team ${chosen.includes(i) ? 'chosen' : ''}`} onClick={() => setChosen(old => old.includes(i) ? old.filter(n => n !== i) : [...old, i])}>{chosen.includes(i) && <Check size={15} className="inline mr-1" />}{name}</button>)}</div><button className="mg-button" onClick={strike}><Shield size={17} />{chosen.length ? 'Нанести общий удар' : 'Разобрали — идём дальше'}</button></>}</div>
    </>}
  </GameFrame>;
}
