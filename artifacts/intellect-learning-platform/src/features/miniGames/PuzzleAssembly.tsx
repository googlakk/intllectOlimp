import { useState } from 'react';
import { Puzzle, Link2 } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { GameError, GameFrame, GameResult } from './GameFrame';
import { puzzleCorrect, readGame, type GameData, type GameProps } from './model';

export default function PuzzleAssembly(props: GameProps) {
  const [session, setSession] = useState(0); const data = readGame('PuzzleAssembly', props);
  return data ? <Assembly key={`${session}:${JSON.stringify(data)}`} data={data} reset={() => setSession(n => n + 1)} /> : <GameError />;
}
function Assembly({ data, reset }: { data: GameData['PuzzleAssembly']; reset: () => void }) {
  const [selected, setSelected] = useState<string | null>(null), [placements, setPlacements] = useState<Record<string, string>>({});
  const [checked, setChecked] = useState(false), [finished, setFinished] = useState(false);
  const pieces = [...data.pieces].reverse();
  const filled = Object.keys(placements).length;
  function place(slot: string) {
    if (finished) return;
    setPlacements(old => { const next = { ...old }; if (selected) next[slot] = selected; else delete next[slot]; return next; });
    setSelected(null); setChecked(false);
  }
  function verify() { if (filled !== data.slots.length) return; setChecked(true); setFinished(puzzleCorrect(data, placements)); }
  return <GameFrame game={data} theme="puzzle" name="Собери целое" onReset={reset}>
    {finished ? <GameResult headline="Все связи на своих местах" takeaway={data.takeaway}><p>Каждый фрагмент помог увидеть общую картину.</p></GameResult> : <>
      <div className="mg-round-label"><span className="flex items-center gap-2"><Link2 size={16} /> КАРТА СВЯЗЕЙ</span><span>{filled} / {data.slots.length}</span></div>
      <div className="mg-puzzle-board">{data.slots.map((slot, i) => { const piece = data.pieces.find(p => p.id === placements[slot.id]); return <button key={slot.id} className={`mg-slot ${piece ? 'filled' : ''} ${selected ? 'waiting' : ''}`} aria-label={`${slot.label}: ${piece?.text ?? 'пустое место'}`} onClick={() => place(slot.id)}><b>0{i + 1} · {slot.label}</b>{piece ? <RichText text={piece.text} /> : <span className="mg-muted">{selected ? 'Поместить фрагмент сюда' : 'Ждёт свою часть'}</span>}</button>; })}</div>
      <p className="mg-muted mt-4">Каждый участник выбирает фрагмент и объясняет его группе. Нажмите фрагмент, затем его место. Нажатие на занятую ячейку без выбора возвращает фрагмент.</p>
      <div className="mg-pieces" aria-label="Фрагменты для сборки">{pieces.filter(piece => !Object.values(placements).includes(piece.id)).map(piece => <button key={piece.id} aria-pressed={selected === piece.id} className={`mg-piece ${selected === piece.id ? 'selected' : ''}`} onClick={() => setSelected(old => old === piece.id ? null : piece.id)}><RichText text={piece.text} /></button>)}</div>
      {checked && !finished && <p role="status" className="mg-feedback">Есть несовпадения. Сверьте смысл фрагментов с названиями ячеек и объясните связи друг другу.</p>}
      <div className="mg-actions"><button className="mg-button" disabled={filled !== data.slots.length} onClick={verify}><Puzzle size={18} /> Проверить общую картину</button><span className="mg-muted">Участвует вся группа</span></div>
    </>}
  </GameFrame>;
}
