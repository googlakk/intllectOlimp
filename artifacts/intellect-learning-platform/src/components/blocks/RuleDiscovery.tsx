import { useState } from 'react';
import { applyHiddenRule, displayNumber, isBoundedNumber, matchingOutputs, parseNumericAnswer, readRuleSpec, type RuleSpec } from '@/features/interactiveEngines/numberMachines';
import { BlockShell, PrimaryAction } from './shared';
import { RichText } from './RichText';

type Props = Record<string, unknown> & { onAnswer?: (correct: boolean) => void };

export default function RuleDiscovery(props: Props) {
  const spec = readRuleSpec(props);
  if (!spec) return <p role="alert" className="p-4">Не удалось открыть правило: проверьте данные задания.</p>;
  return <RuleSession key={JSON.stringify(spec)} spec={spec} title={typeof props.title === 'string' ? props.title : 'Скрытое правило'} prompt={typeof props.prompt === 'string' ? props.prompt : ''} explanation={typeof props.explanation === 'string' ? props.explanation : ''} onAnswer={props.onAnswer} />;
}

function RuleSession({ spec, title, prompt, explanation, onAnswer }: { spec: RuleSpec; title: string; prompt: string; explanation: string; onAnswer?: (correct: boolean) => void }) {
  const [history, setHistory] = useState(spec.examples);
  const [probe, setProbe] = useState('');
  const [hypothesis, setHypothesis] = useState('');
  const [answers, setAnswers] = useState<string[]>(spec.challenge_inputs.map(() => ''));
  const [feedback, setFeedback] = useState('');
  const [correct, setCorrect] = useState(false);
  const input = parseNumericAnswer(probe);
  const probeAllowed = input !== null && isBoundedNumber(input) && !spec.challenge_inputs.includes(input) && applyHiddenRule(spec.rule, input) !== null;
  const check = () => {
    const predicted = answers.map(parseNumericAnswer);
    if (predicted.some((value) => value === null)) return;
    const expected = spec.challenge_inputs.map((value) => applyHiddenRule(spec.rule, value) as number);
    const success = matchingOutputs(predicted as number[], expected);
    setCorrect(success);
    setFeedback(success ? 'Все прогнозы совпали! Обсудите, почему правило работает.' : 'Пока не все прогнозы совпали. Проверьте гипотезу на новых числах.');
    onAnswer?.(success);
  };
  return <BlockShell title={title} subtitle={prompt}>
    <div className="rounded-2xl bg-slate-950 p-4 text-white sm:p-6">
      <div className="flex items-center justify-center gap-3 py-5" aria-label="Число проходит через скрытое правило">
        <span className="rounded-xl border border-cyan-300/50 bg-cyan-300/10 px-3 py-4 text-2xl font-mono">x</span>
        <span aria-hidden="true">→</span>
        <div className="rounded-2xl border-2 border-violet-400 bg-violet-500/20 px-7 py-4 text-4xl font-bold shadow-lg shadow-violet-500/20">?</div>
        <span aria-hidden="true">→</span>
        <span className="rounded-xl border border-amber-300/50 bg-amber-300/10 px-3 py-4 text-2xl font-mono">y</span>
      </div>
      <p className="mb-3 text-xs uppercase tracking-widest text-slate-300">Журнал наблюдений</p>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3" aria-live="polite">
        {history.map((value, index) => <div key={index} className="flex min-w-0 flex-wrap items-center justify-between gap-1 rounded-lg bg-white/10 px-3 py-2 font-mono text-sm"><span className="text-cyan-200">{displayNumber(value)}</span><span aria-hidden="true">→</span><span className="text-amber-200">{displayNumber(applyHiddenRule(spec.rule, value) as number)}</span></div>)}
      </div>
      <form className="mt-4 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); if (probeAllowed && input !== null) { setHistory((current) => [...current.slice(-11), input]); setProbe(''); } }}>
        <input aria-label="Число для эксперимента" placeholder="Число от −100 до 100" inputMode="decimal" value={probe} onChange={(event) => setProbe(event.target.value)} className="min-w-0 flex-1 rounded-lg border border-slate-500 bg-slate-900 px-3 py-3 text-base" />
        <button disabled={!probeAllowed} className="rounded-lg bg-cyan-300 px-4 py-3 font-bold text-slate-950 disabled:opacity-40">Испытать</button>
      </form>
      <p className="mt-2 text-xs text-slate-300">Числа из финального прогноза закрыты для эксперимента.</p>
    </div>
    <label className="mt-5 block text-sm font-semibold">Моя гипотеза <span className="font-normal text-muted-foreground">(необязательно, обсуждаем устно)</span><textarea value={hypothesis} onChange={(event) => setHypothesis(event.target.value)} rows={2} maxLength={500} className="mt-2 w-full rounded-lg border bg-background p-3 text-base" placeholder="Мне кажется, машина…" /></label>
    <fieldset className="mt-4"><legend className="mb-3 font-semibold">Предскажите выход для новых чисел</legend><div className="grid gap-3 sm:grid-cols-3">{spec.challenge_inputs.map((value, index) => <label key={index} className="flex min-w-0 items-center gap-2 rounded-lg border p-3"><span className="shrink-0 font-mono">{displayNumber(value)} →</span><input aria-label={`Прогноз для ${value}`} inputMode="decimal" value={answers[index]} onChange={(event) => { setAnswers((current) => current.map((answer, position) => position === index ? event.target.value : answer)); setFeedback(''); setCorrect(false); }} className="w-full min-w-0 rounded-md border bg-background p-2 text-base" /></label>)}</div></fieldset>
    <div className="mt-4"><PrimaryAction disabled={answers.some((value) => parseNumericAnswer(value) === null)} onClick={check}>Проверить прогноз</PrimaryAction></div>
    <div role="status" className={`mt-3 text-sm ${correct ? 'text-emerald-700' : 'text-muted-foreground'}`}>{feedback}</div>
    {correct && <RichText text={explanation} className="mt-3 rounded-lg bg-emerald-50 p-4 text-slate-900" />}
  </BlockShell>;
}
