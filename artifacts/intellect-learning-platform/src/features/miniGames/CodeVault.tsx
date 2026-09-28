import { useState } from 'react';
import { KeyRound, LockKeyhole } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { ChoiceButtons, GameError, GameFrame, GameResult } from './GameFrame';
import { readGame, type GameData, type GameProps } from './model';

export default function CodeVault(props: GameProps) {
  const [session, setSession] = useState(0); const data = readGame('CodeVault', props);
  return data ? <Vault key={`${session}:${JSON.stringify(data)}`} data={data} reset={() => setSession(n => n + 1)} /> : <GameError />;
}
function Vault({ data, reset }: { data: GameData['CodeVault']; reset: () => void }) {
  const [active, setActive] = useState(0), [solved, setSolved] = useState<number[]>([]);
  const [choices, setChoices] = useState<Record<number, number>>({}), [checked, setChecked] = useState<Record<number, boolean>>({});
  const [opened, setOpened] = useState(false), [started, setStarted] = useState(false);
  const clue = data.clues[active], done = solved.length === data.clues.length;
  function verify() {
    if (choices[active] === undefined || solved.includes(active)) return;
    const correct = choices[active] === clue.correct_index;
    setChecked(old => ({ ...old, [active]: correct }));
    if (correct) setSolved(old => [...old, active]);
  }
  return <GameFrame game={data} theme="vault" name="Секретный код" onReset={reset}>
    <div className="mg-vault-door"><div className="mg-tumblers">{data.clues.map((item, i) => <span aria-label={`Цифра ${i + 1}: ${solved.includes(i) ? item.digit : 'закрыта'}`} key={i} className={`mg-tumbler ${solved.includes(i) ? 'unlocked' : ''}`}>{solved.includes(i) ? item.digit : '•'}</span>)}</div><p className="mg-vault-label">{opened ? 'ДОСТУП ОТКРЫТ' : `${solved.length} ИЗ ${data.clues.length} КЛЮЧЕЙ НАЙДЕНО`}</p></div>
    {opened ? <GameResult headline="Код собран. Сейф ваш!" takeaway={data.takeaway} /> : !started ? <><p className="mg-question">Один сейф. Несколько экспертов.</p><p className="mg-muted">Распределите улики между участниками группы. Каждый объясняет свою часть, а решение выбираете вместе.</p><div className="mg-actions"><button className="mg-button" onClick={() => setStarted(true)}><LockKeyhole size={18} /> Получить улики</button></div></> : <>
      <div className="mg-tabs" aria-label="Улики">{data.clues.map((item, i) => <button key={i} aria-pressed={active === i} onClick={() => setActive(i)} className={`mg-tab ${active === i ? 'active' : ''}`}>{solved.includes(i) ? '✓' : `0${i + 1}`} · {item.label}</button>)}</div>
      <div className="mg-panel"><span className="mg-eyebrow">ЭКСПЕРТ {active + 1} · ОБЪЯСНИ СВОЮ УЛИКУ</span><RichText className="mg-question" text={clue.question} /><ChoiceButtons options={clue.options} selected={choices[active] ?? null} disabled={solved.includes(active)} onSelect={i => { setChoices(old => ({ ...old, [active]: i })); setChecked(old => { const next = { ...old }; delete next[active]; return next; }); }} />
        {checked[active] !== undefined && <div className="mg-feedback" role="status">{checked[active] ? <><strong>Ключ получен: {clue.digit}</strong><RichText text={clue.explanation} /></> : 'Замок не поддался. Обсудите другой вариант и попробуйте ещё раз.'}</div>}
        <div className="mg-actions">{!solved.includes(active) && <button className="mg-button" disabled={choices[active] === undefined} onClick={verify}>Проверить улику</button>}{done ? <button className="mg-button" onClick={() => setOpened(true)}><KeyRound size={18} /> Открыть сейф</button> : solved.includes(active) && <button className="mg-button" onClick={() => setActive(data.clues.findIndex((_, i) => !solved.includes(i)))}>К следующему эксперту →</button>}</div>
      </div>
    </>}
  </GameFrame>;
}
