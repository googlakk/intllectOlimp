import { useState } from 'react';
import { displayNumber, matchingOutputs, readMachineSpec, runMachine, type MachineSpec } from '@/features/interactiveEngines/numberMachines';
import { BlockShell, PrimaryAction } from './shared';
import { RichText } from './RichText';

type Props = Record<string, unknown> & { onAnswer?: (correct: boolean) => void };
export default function TransformationMachine(props: Props) {
  const spec = readMachineSpec(props);
  if (!spec) return <p role="alert" className="p-4">Не удалось открыть фабрику: проверьте операции и образец решения.</p>;
  return <MachineSession key={JSON.stringify(spec)} spec={spec} title={typeof props.title === 'string' ? props.title : 'Фабрика преобразований'} prompt={typeof props.prompt === 'string' ? props.prompt : ''} explanation={typeof props.explanation === 'string' ? props.explanation : ''} onAnswer={props.onAnswer} />;
}

function MachineSession({ spec, title, prompt, explanation, onAnswer }: { spec: MachineSpec; title: string; prompt: string; explanation: string; onAnswer?: (correct: boolean) => void }) {
  const [sequence, setSequence] = useState<string[]>([]);
  const [stages, setStages] = useState<number[][] | null>(null);
  const [tries, setTries] = useState(0);
  const [message, setMessage] = useState('');
  const [correct, setCorrect] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const edit = (next: string[]) => { setSequence(next); setStages(null); setMessage(''); setCorrect(false); };
  const move = (index: number, direction: number) => {
    const next = [...sequence];
    const target = index + direction;
    if (target < 0 || target >= next.length) return;
    [next[index], next[target]] = [next[target], next[index]];
    edit(next);
  };
  const run = () => {
    const result = runMachine(spec, sequence);
    setTries((value) => value + 1);
    setStages(result);
    const success = result !== null && matchingOutputs(result[result.length - 1], spec.target_outputs);
    setCorrect(success);
    setMessage(result === null ? 'Числа вышли за допустимый диапазон. Попробуйте другую цепочку.' : success ? 'Фабрика работает: все выходы совпали с целью!' : 'Выходы отличаются от цели. Измените операции или их порядок.');
    onAnswer?.(success);
  };
  return <BlockShell title={title} subtitle={prompt}>
    <div className="grid grid-cols-2 gap-3">
      <div className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-slate-900"><p className="mb-2 text-xs font-bold uppercase tracking-wider">На входе</p><div className="flex flex-wrap gap-2">{spec.inputs.map((value, index) => <span key={index} className="rounded-md bg-white px-3 py-2 font-mono font-bold">{displayNumber(value)}</span>)}</div></div>
      <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-slate-900"><p className="mb-2 text-xs font-bold uppercase tracking-wider">Нужный выход</p><div className="flex flex-wrap gap-2">{spec.target_outputs.map((value, index) => <span key={index} className="rounded-md bg-white px-3 py-2 font-mono font-bold">{displayNumber(value)}</span>)}</div></div>
    </div>
    <p className="mb-3 mt-5 text-sm font-semibold">Добавьте станки. Каждый можно использовать несколько раз.</p>
    <div className="flex flex-wrap gap-2">{spec.operations.map((operation) => <button key={operation.id} disabled={sequence.length >= spec.max_steps} onClick={() => edit([...sequence, operation.id])} className="rounded-lg border-2 border-amber-300 bg-amber-50 px-4 py-3 text-sm font-bold text-slate-900 disabled:opacity-40">+ {operation.label}</button>)}</div>
    <div className="mt-5 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 p-3 text-slate-900">
      <p className="mb-3 text-xs font-bold uppercase tracking-widest">Конвейер · {sequence.length}/{spec.max_steps}</p>
      {sequence.length === 0 && <p className="py-6 text-center text-sm text-slate-500">Выберите первый станок выше</p>}
      <ol className="space-y-2">{sequence.map((id, index) => <li key={index} className="rounded-lg border border-slate-200 bg-white p-3">
        <div className="flex flex-wrap items-center gap-2"><span className="rounded bg-slate-900 px-2 py-1 text-xs text-white">{index + 1}</span><span className="min-w-0 flex-1 break-words font-semibold">{spec.operations.find((operation) => operation.id === id)?.label}</span><div className="flex gap-1">
          <button aria-label={`Шаг ${index + 1}: выше`} disabled={index === 0} onClick={() => move(index, -1)} className="rounded border px-3 py-2 disabled:opacity-30">↑</button>
          <button aria-label={`Шаг ${index + 1}: ниже`} disabled={index === sequence.length - 1} onClick={() => move(index, 1)} className="rounded border px-3 py-2 disabled:opacity-30">↓</button>
          <button aria-label={`Удалить шаг ${index + 1}`} onClick={() => edit(sequence.filter((_, position) => position !== index))} className="rounded border px-3 py-2">×</button>
        </div></div>
        {stages && <div className="mt-2 flex flex-wrap gap-2 border-t pt-2" aria-label={`После шага ${index + 1}`}>{stages[index + 1].map((value, position) => <span key={position} className="rounded bg-cyan-50 px-2 py-1 font-mono text-sm">{displayNumber(stages[index][position])} → {displayNumber(value)}</span>)}</div>}
      </li>)}</ol>
    </div>
    <div className="mt-4 flex flex-wrap gap-3"><PrimaryAction disabled={sequence.length === 0} onClick={run}>Запустить и проверить</PrimaryAction><button onClick={() => edit([])} className="rounded-lg border px-4 py-2 text-sm">Очистить конвейер</button></div>
    <p role="status" className={`mt-3 text-sm ${correct ? 'text-emerald-700' : 'text-muted-foreground'}`}>{message}</p>
    {tries >= 2 && !correct && !revealed && <button onClick={() => setRevealed(true)} className="mt-3 rounded-lg border px-4 py-2 text-sm">Показать образец решения</button>}
    {revealed && <div className="mt-3 rounded-lg bg-amber-50 p-4 text-sm text-slate-900"><p className="font-semibold">Образец: {spec.solution.map((id) => spec.operations.find((operation) => operation.id === id)?.label).join(' → ')}</p><p className="mt-1">Соберите цепочку и объясните каждый шаг.</p></div>}
    {(correct || revealed) && <RichText text={explanation} className="mt-3 text-sm" />}
  </BlockShell>;
}
