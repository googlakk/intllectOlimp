import { Check, Lightbulb } from 'lucide-react';
import { useState } from 'react';
import type { SampleAnswer, SampleQuestionData } from './sampleModel';

export function SampleQuestion({ id, question, answer, onAnswer }: { id: string; question: SampleQuestionData; answer?: SampleAnswer; onAnswer: (choice: number) => void }) {
  const [help, setHelp] = useState(false);
  const correct = answer?.choice === question.correct;
  return <section className="sample-question" aria-labelledby={`question-${id}`}>
    <h2 id={`question-${id}`}>{question.prompt}</h2>
    <div className="sample-choices">{question.options.map((option, i) => <button type="button" key={option} disabled={correct} onClick={() => onAnswer(i)} className={answer?.choice === i ? correct ? 'is-correct' : 'is-wrong' : ''}><span className="sample-option-letter">{correct && answer?.choice === i ? <Check size={17} /> : String.fromCharCode(65 + i)}</span><span>{option}</span></button>)}</div>
    <div aria-live="polite">{answer && <div className={`sample-feedback ${correct ? 'is-correct' : ''}`}><strong>{correct ? 'Верно. Вот почему.' : 'Эта версия требует пересмотра.'}</strong><p>{correct || help ? question.explanation : 'Вернись к условиям и сравни варианты. Можно попробовать ещё раз или открыть разбор.'}</p></div>}</div>
    {!correct && <button type="button" className="sample-help" onClick={() => setHelp(!help)} aria-expanded={help}><Lightbulb size={16} />{help ? 'Скрыть разбор' : 'Разобраться вместе'}</button>}
    {help && !answer && <p className="sample-note">{question.explanation}</p>}
  </section>;
}
