import { useState } from 'react';
import { Check, ArrowRight, Lightbulb } from 'lucide-react';
import { answerFeedback, questions, type QuestionId, type Response } from './model';

export function GardenQuestion({ id, response, onAnswer }: { id: QuestionId; response?: Response; onAnswer: (value: number) => void }) {
  const [input, setInput] = useState(response ? String(response.value) : '');
  const [hint, setHint] = useState(false);
  const question = questions[id];
  const number = Number(input.trim().replace(',', '.'));
  return <div className="garden-question">
    <h2>{question.prompt}</h2>
    {question.options.length > 0 ? <div className="garden-answers" aria-label="Варианты ответа">{question.options.map(value => <button key={value} disabled={response?.correct} className={response?.value === value ? response.correct ? 'is-correct' : 'is-wrong' : ''} onClick={() => onAnswer(value)}>{value.toLocaleString('ru')} {question.unit}{response?.value === value && response.correct && <Check size={20} />}</button>)}</div> : <form onSubmit={event => { event.preventDefault(); if (input.trim() && Number.isFinite(number)) onAnswer(number); }} className="garden-answer-input"><label htmlFor="garden-answer">Сторона площадки, м</label><div><input id="garden-answer" inputMode="decimal" autoComplete="off" value={input} disabled={response?.correct} placeholder="Твой ответ" onChange={event => setInput(event.target.value)} /><button className="garden-primary" disabled={response?.correct || !input.trim() || !Number.isFinite(number)} type="submit">Проверить <ArrowRight size={18} /></button></div></form>}
    <div aria-live="polite">{response && <div className={`garden-feedback ${response.correct ? 'is-correct' : ''}`}><strong>{response.correct ? 'Да, всё сходится.' : 'Давай проверим эту идею.'}</strong><p>{answerFeedback(id, response)}</p></div>}</div>
    {!response?.correct && <><button className="garden-hint" onClick={() => setHint(!hint)} aria-expanded={hint}><Lightbulb size={17} />{hint ? 'Скрыть подсказку' : 'Небольшая подсказка'}</button>{hint && <p className="garden-note">{id === 'predict' ? 'Вспомни таблицу умножения: какое число при умножении на себя даёт 25?' : id === 'trap' ? 'Вычислить корень — найти неотрицательное число, квадрат которого равен исходному числу.' : 'Ищи два одинаковых множителя. 6 × 6 = 36 — мало, а 8 × 8 = 64 — много.'}</p>}</>}
  </div>;
}
