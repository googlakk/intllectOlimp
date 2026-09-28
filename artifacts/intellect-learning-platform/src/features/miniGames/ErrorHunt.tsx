import { useState } from 'react';
import { Check, ScanLine, Wrench } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { ChoiceButtons, GameError, GameFrame, GameResult } from './GameFrame';
import { readGame, repairsCorrect, type GameData, type GameProps } from './model';

export default function ErrorHunt(props: GameProps) {
  const [session, setSession] = useState(0); const data = readGame('ErrorHunt', props);
  return data ? <Hunt key={`${session}:${JSON.stringify(data)}`} data={data} reset={() => setSession(n => n + 1)} onAnswer={props.onAnswer} /> : <GameError />;
}
function Hunt({ data, reset, onAnswer }: { data: GameData['ErrorHunt']; reset: () => void; onAnswer?: (v: boolean) => void }) {
  const [answers, setAnswers] = useState<Record<number, number>>({}), [suspect, setSuspect] = useState<number | null>(null);
  const [checked, setChecked] = useState(false), [done, setDone] = useState(false);
  function decide(line: number, answer: number) { setAnswers(old => ({ ...old, [line]: answer })); setChecked(false); }
  function verify() {
    if (Object.keys(answers).length !== data.lines.length || done) return;
    const success = repairsCorrect(data, answers); setChecked(true); setDone(success); onAnswer?.(success);
  }
  return <GameFrame game={data} theme="errors" name="Почини решение" group={false} onReset={reset}>
    {done ? <GameResult headline="Проверено. Исправлено. Понятно." takeaway={data.takeaway}>{data.lines.filter(line => line.is_error).map((line, i) => <div key={i} className="mg-takeaway"><RichText text={line.fixes[line.correct_index!]} /><RichText className="mg-muted mt-2" text={line.explanation} /></div>)}</GameResult> : <>
      <div className="mg-lab-head"><div className="mg-lab-lights" aria-hidden="true"><i /><i /><i /></div><span>ЛАБОРАТОРИЯ / ПРОВЕРКА МЫСЛИ</span><ScanLine size={16} /></div>
      <div className="mg-code-lines">{data.lines.map((line, i) => { const answer = answers[i]; const correct = answer === (line.is_error ? line.correct_index : -1); return <div key={i} className={`mg-code-line ${answer >= 0 ? 'repaired' : suspect === i ? 'flagged' : ''}`}><span className="mg-line-no">{String(i + 1).padStart(2, '0')}</span><div><RichText text={answer >= 0 ? line.fixes[answer] : line.text} />{answer >= 0 && <span className="mg-repair-marker"><Wrench size={13} /> Предложено исправление</span>}<div className="mg-line-actions"><button aria-pressed={answer === -1} onClick={() => { decide(i, -1); setSuspect(null); }}>✓ Здесь всё верно</button><button aria-pressed={suspect === i || answer >= 0 || answer === -2} onClick={() => { setSuspect(i); if (answer === undefined || answer === -1) decide(i, -2); }}>Найти исправление</button></div>
        {suspect === i && line.fixes.length > 0 && <ChoiceButtons options={line.fixes} selected={answer >= 0 ? answer : null} onSelect={n => { decide(i, n); setSuspect(null); }} />}
        {suspect === i && line.fixes.length === 0 && <p className="mg-muted mt-2">Строка отмечена как подозрительная. Проверка покажет, нужно ли её менять.</p>}
        {checked && <div className="mg-feedback" role="status"><strong>{correct ? 'Верно проверено' : 'Эта строка требует внимания'}</strong><RichText text={line.explanation} /></div>}
      </div></div>; })}</div>
      <p className="mg-muted mt-4">Некоторые строки верны. Проверь каждую: оставь её или выбери исправление.</p><div className="mg-actions"><button className="mg-button" disabled={Object.keys(answers).length !== data.lines.length} onClick={verify}><Check size={18} /> Проверить исправления</button><span className="mg-muted">Проверено {Object.keys(answers).length} / {data.lines.length}</span></div>
    </>}
  </GameFrame>;
}
