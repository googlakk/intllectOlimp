import { useState } from 'react';
import { Coins, Gavel } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { GameError, GameFrame, GameResult, TeamCount } from './GameFrame';
import { readGame, settleAuction, TEAM_NAMES, type GameData, type GameProps } from './model';

export default function KnowledgeAuction(props: GameProps) {
  const [session, setSession] = useState(0); const data = readGame('KnowledgeAuction', props);
  return data ? <Auction key={`${session}:${JSON.stringify(data)}`} data={data} reset={() => setSession(n => n + 1)} /> : <GameError />;
}
function Auction({ data, reset }: { data: GameData['KnowledgeAuction']; reset: () => void }) {
  const [teams, setTeams] = useState(3), [started, setStarted] = useState(false), [round, setRound] = useState(0);
  const [coins, setCoins] = useState<number[]>(Array(6).fill(10)), [scores, setScores] = useState<number[]>(Array(6).fill(0));
  const [bids, setBids] = useState<number[]>(Array(6).fill(0)), [approved, setApproved] = useState<boolean[]>(Array(6).fill(false)), [revealed, setRevealed] = useState(false);
  const done = round === data.statements.length, item = data.statements[round];
  function settle() {
    if (!revealed || done) return;
    const result = settleAuction(coins, scores, bids, approved, item.is_true);
    setCoins(result.coins); setScores(result.scores); setBids(Array(6).fill(0)); setApproved(Array(6).fill(false)); setRevealed(false); setRound(n => n + 1);
  }
  const best = Math.max(...scores.slice(0, teams));
  return <GameFrame game={data} theme="auction" name="Аукцион утверждений" onReset={reset}>
    {done ? <GameResult headline={best ? 'Знания дороже золота' : 'Главная покупка — опыт'} takeaway={data.takeaway}><div className="mg-teams">{scores.slice(0, teams).map((score, i) => <div key={i} className={`mg-team ${score === best && best > 0 ? 'chosen' : ''}`}>{TEAM_NAMES[i]}<strong>{score} очков</strong><small>Осталось {coins[i]} монет</small></div>)}</div></GameResult> : <>
      <div className="mg-auction-lot"><div className="mg-lot-top"><span>КОЛЛЕКЦИЯ ЗНАНИЙ</span><Gavel size={24} /></div><div className="mg-question"><RichText text={started ? item.text : 'Не всё, что звучит убедительно, стоит ваших монет.'} /></div>{revealed ? <span className={`mg-stamp ${item.is_true ? '' : 'false'}`}>{item.is_true ? 'Подлинное знание' : 'Подделка'}</span> : <div className="mg-lot-top"><span>ЛОТ № {String(round + 1).padStart(2, '0')}</span><span>СТАВКА 0–3</span></div>}</div>
      {!started ? <><p className="mg-muted">У каждой команды 10 монет. Ставьте до 3 на верное утверждение или пропускайте. Монеты тратятся; обоснованная покупка верного факта приносит вдвое больше очков.</p><div className="mg-actions"><TeamCount value={teams} onChange={setTeams} /><button className="mg-button" onClick={() => setStarted(true)}>Открыть торги</button></div></> : <>
        <div className="mg-round-label"><span>ЛОТ {round + 1} ИЗ {data.statements.length}</span><span>{revealed ? 'Ставки закрыты' : 'Сначала обсудите в командах'}</span></div>
        <div className="mg-teams">{TEAM_NAMES.slice(0, teams).map((name, i) => <div className="mg-team" key={name}><b>{name}</b><div className="mg-coins"><Coins size={13} /> {coins[i]} монет · {scores[i]} очков</div><div className="mg-bid"><button aria-label={`Уменьшить ставку: ${name}`} disabled={revealed || bids[i] === 0} onClick={() => setBids(old => old.map((n, j) => j === i ? n - 1 : n))}>−</button><output aria-label={`Ставка: ${name}`}>{bids[i]}</output><button aria-label={`Увеличить ставку: ${name}`} disabled={revealed || bids[i] >= Math.min(3, coins[i])} onClick={() => setBids(old => old.map((n, j) => j === i ? n + 1 : n))}>+</button></div>{revealed && item.is_true && bids[i] > 0 && <label className="mt-3 flex items-start gap-2 text-xs"><input type="checkbox" checked={approved[i]} onChange={e => setApproved(old => old.map((v, j) => j === i ? e.target.checked : v))} />Объяснение принято</label>}</div>)}</div>
        {revealed && <div className="mg-feedback"><RichText text={item.explanation} />{item.is_true && <p className="mg-muted mt-2">Учитель отмечает команды, которые обосновали покупку.</p>}</div>}
        <button className="mg-button" onClick={() => revealed ? settle() : setRevealed(true)}><Gavel size={17} />{revealed ? round === data.statements.length - 1 ? 'Подвести итоги' : 'Рассчитать лот →' : 'Закрыть ставки и проверить'}</button>
      </>}
    </>}
  </GameFrame>;
}
