import { useMemo, useState } from 'react';
import katex from 'katex';
import { CheckCircle2, Eye, Lightbulb, XCircle } from 'lucide-react';
import { BlockShell, PrimaryAction } from './shared';
import { RichText } from './RichText';
import MathAnswerInput from './MathAnswerInput';
import { mathLineToLatex } from '@/features/interactiveEngines/mathExpression';
import { checkStep, normalizeSolver, type StepVerdict } from '@/features/interactiveEngines/stepSolver';
import type { BlockAttempt } from '@/features/tutor/tutorBridge';

export interface StepSolverProps {
  title?: string;
  instruction?: string;
  kind?: 'expression' | 'equation';
  start: string;
  steps?: unknown;
  final_answer: string | string[];
  answer_mode?: 'form' | 'equivalent';
  mistakes?: unknown;
  explanation?: string;
  onAnswer?: (isCorrect: boolean) => void;
  onAttempt?: (attempt: BlockAttempt) => void;
}

// После двух неверных строк подряд можно открыть следующий шаг образца.
const REVEAL_AFTER = 2;

/** Строка решения «как в тетради»; не разобралась — как текст урока. */
function MathLine({ text }: { text: string }) {
  const html = useMemo(() => {
    const latex = mathLineToLatex(text);
    if (!latex) return null;
    try {
      return katex.renderToString(latex, { throwOnError: false });
    } catch {
      return null;
    }
  }, [text]);
  return html ? <span dangerouslySetInnerHTML={{ __html: html }} /> : <RichText text={text} inline />;
}

const FEEDBACK: Record<Exclude<StepVerdict['status'], 'ok' | 'mistake'>, string> = {
  wrong: 'Эта строка не равна предыдущей. Проверь преобразование — или открой подсказку.',
  unreadable: 'Не получается прочитать запись. Пиши как в тетради: 2√3, 3/4, x^2, 3x − 6 = x + 4.',
};

export default function StepSolver({ title, instruction, kind, start, steps, final_answer, answer_mode, mistakes, explanation, onAnswer, onAttempt }: StepSolverProps) {
  const spec = useMemo(
    () => normalizeSolver({ kind, start, steps, final_answer, answer_mode, mistakes }),
    [kind, start, steps, final_answer, answer_mode, mistakes],
  );
  const [lines, setLines] = useState<{ text: string; shown: boolean }[]>([]);
  const [value, setValue] = useState('');
  const [feedback, setFeedback] = useState<string | null>(null);
  const [misses, setMisses] = useState(0);
  const [hintOpen, setHintOpen] = useState(false);
  const [hintsSeen, setHintsSeen] = useState(0);
  const [done, setDone] = useState(false);

  if (!spec) {
    return <BlockShell title={title || 'Решаю по шагам'}><p className="text-sm text-muted-foreground">Задание собрано с ошибкой — сообщите учителю.</p></BlockShell>;
  }

  const stepIndex = Math.min(lines.length, Math.max(spec.steps.length - 1, 0));
  const nextStep = spec.steps[stepIndex];
  const revealed = lines.filter((line) => line.shown).length;

  const finish = (withHelp: boolean) => {
    setDone(true);
    onAnswer?.(!withHelp);
  };

  const accept = (text: string, shown: boolean, isDone: boolean) => {
    setLines((current) => [...current, { text, shown }]);
    setValue('');
    setFeedback(null);
    setMisses(0);
    setHintOpen(false);
    if (isDone) finish(shown || revealed > 0);
  };

  const submit = () => {
    const text = value.trim();
    if (!text || done) return;
    const verdict = checkStep(text, spec);
    onAttempt?.({ value: text, outcome: verdict.status === 'ok' ? 'correct' : 'incorrect', hintsSeen });
    if (verdict.status === 'ok') {
      accept(text, false, verdict.done);
      return;
    }
    setMisses((count) => count + 1);
    setFeedback(verdict.status === 'mistake' ? verdict.message : FEEDBACK[verdict.status]);
  };

  const showStep = () => {
    if (!nextStep) return;
    const verdict = checkStep(nextStep.expected, spec);
    accept(nextStep.expected, true, verdict.status === 'ok' && verdict.done);
  };

  return (
    <BlockShell title={title || 'Решаю по шагам'} subtitle={instruction || 'Пиши решение строка за строкой: каждое преобразование проверяется сразу.'}>
      <ol className="space-y-2 rounded-lg border bg-muted/20 p-4 text-lg" aria-label="Решение">
        <li className="flex items-baseline gap-3">
          <span className="w-16 shrink-0 text-xs font-medium text-muted-foreground">Задание</span>
          <MathLine text={spec.start} />
        </li>
        {lines.map((line, index) => (
          <li key={index} className="flex items-baseline gap-3">
            <span className="w-16 shrink-0 text-xs font-medium text-muted-foreground">{line.shown ? 'Образец' : `Шаг ${index + 1}`}</span>
            <MathLine text={line.text} />
            {!line.shown && <CheckCircle2 className="h-4 w-4 shrink-0 self-center text-green-600" aria-label="верно" />}
          </li>
        ))}
      </ol>

      {!done && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
            <MathAnswerInput
              value={value}
              onChange={(next) => { setValue(next); setFeedback(null); }}
              onEnter={submit}
              mathTools
              placeholder={spec.kind === 'equation' ? 'Следующая строка, например 3x − 6 = x + 4' : 'Следующая строка'}
            />
            <PrimaryAction onClick={submit} disabled={!value.trim()}>Проверить шаг</PrimaryAction>
          </div>

          {feedback && (
            <div role="status" className="flex items-start gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm font-medium text-destructive">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <RichText text={feedback} inline />
            </div>
          )}

          <div className="flex flex-wrap gap-3 text-sm">
            {nextStep?.hint && !hintOpen && (
              <button type="button" onClick={() => { setHintOpen(true); setHintsSeen((count) => count + 1); }}
                className="inline-flex min-h-9 items-center gap-1.5 py-2 font-medium text-primary hover:text-primary/80">
                <Lightbulb className="h-4 w-4" /> Какое преобразование?
              </button>
            )}
            {nextStep && misses >= REVEAL_AFTER && (
              <button type="button" onClick={showStep} className="inline-flex min-h-9 items-center gap-1.5 py-2 font-medium text-muted-foreground hover:text-foreground">
                <Eye className="h-4 w-4" /> Показать этот шаг
              </button>
            )}
          </div>
          {hintOpen && nextStep?.hint && (
            <p className="rounded-lg border bg-muted/40 p-3 text-sm text-muted-foreground"><RichText text={nextStep.hint} inline /></p>
          )}
        </div>
      )}

      {done && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center gap-2 rounded-lg border border-green-500/20 bg-green-500/10 p-3.5 text-sm font-medium text-green-700 dark:text-green-400">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            {revealed ? 'Решение готово. Попробуй похожую задачу сам — без образца.' : 'Верно! Ты решил задачу сам.'}
          </div>
          {explanation && <div className="rounded-lg border bg-muted/30 p-4 text-sm"><RichText text={explanation} /></div>}
        </div>
      )}
    </BlockShell>
  );
}
