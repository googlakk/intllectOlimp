import { useState } from 'react';
import { Mountain, Signpost, ArrowRight } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { ChoiceButtons, GameError, GameFrame, GameResult } from './GameFrame';
import { readGame, type GameData, type GameProps } from './model';

export default function LearningPath(props: GameProps) {
  const [session, setSession] = useState(0); const data = readGame('LearningPath', props);
  return data ? <Journey key={`${session}:${JSON.stringify(data)}`} data={data} reset={() => setSession(n => n + 1)} onAnswer={props.onAnswer} /> : <GameError />;
}
function Journey({ data, reset, onAnswer }: { data: GameData['LearningPath']; reset: () => void; onAnswer?: (v: boolean) => void }) {
  const [step, setStep] = useState(0), [route, setRoute] = useState<'support' | 'challenge' | null>(null);
  const [answer, setAnswer] = useState<number | null>(null), [checked, setChecked] = useState<boolean | null>(null);
  const [paths, setPaths] = useState<string[]>([]);
  const done = step === data.checkpoints.length, point = data.checkpoints[step];
  const question = !done && route ? point[route] : null;
  function verify() { if (!question || answer === null) return; const ok = answer === question.correct_index; setChecked(ok); if (!ok) onAnswer?.(false); }
  function next() {
    if (checked !== true || !route || done) return;
    setPaths(old => [...old, route]); setStep(n => n + 1); setRoute(null); setAnswer(null); setChecked(null);
    if (step === data.checkpoints.length - 1) onAnswer?.(true);
  }
  return <GameFrame game={data} theme="path" name="Мой маршрут" group={false} onReset={reset}>
    <div className="mg-route-map"><span className="mg-map-caption">ЭКСПЕДИЦИЯ ПО ТЕМЕ</span><svg viewBox="0 0 560 185" aria-label={`Пройдено ${step} из 3 остановок`} role="img"><path d="m0 185 80-70 50 24 95-104 82 75 72-53 74 71 56-24 51 61" fill="#c3d3ab"/><path d="m215 36-36 40 42-9 29 3Z" fill="#f1f2df"/><path d="M55 154C160 174 138 75 267 106S366 27 490 53" fill="none" stroke="#90a37c" strokeWidth="9" strokeLinecap="round"/><path d="M55 154C160 174 138 75 267 106S366 27 490 53" fill="none" stroke="#fff9e7" strokeWidth="4" strokeDasharray="4 12" strokeLinecap="round"/>{[[88, 152], [267, 106], [466, 54]].map(([x, y], i) => <g key={i}><circle cx={x} cy={y} r={i === step ? 22 : 18} fill={i < step ? '#35664a' : '#fffef5'} stroke={i === step ? '#35664a' : '#9baa88'} strokeWidth="3"/><text x={x} y={y + 5} textAnchor="middle" fill={i < step ? '#fff' : '#35664a'} fontSize="15" fontWeight="800">{i < step ? '✓' : i + 1}</text></g>)}<path d="M499 24v39m0-39 22 8-22 7" stroke="#35664a" strokeWidth="3" fill="#dfa259"/></svg></div>
    {done ? <GameResult headline="Твоя вершина достигнута" takeaway={data.takeaway}><p>3 остановки пройдены · {paths.filter(p => p === 'challenge').length} маршрута с вызовом</p></GameResult> : <>
      <div className="mg-round-label"><span>ОСТАНОВКА {step + 1} / 3</span><span>{point.label}</span></div>
      {!route ? <><p className="mg-question">Как пойдём дальше?</p><p className="mg-muted">Оба пути ведут к одной цели. На каждой остановке можно выбирать заново.</p><div className="mg-route-choices"><button className="mg-route-choice" onClick={() => setRoute('support')}><Signpost /><strong>Уверенный шаг</strong><span>Понятная задача с опорой на изученное</span></button><button className="mg-route-choice challenge" onClick={() => setRoute('challenge')}><Mountain /><strong>Беру высоту</strong><span>Применение знаний в новом примере</span></button></div></> : question && <div className="mg-panel"><span className="mg-eyebrow">{route === 'support' ? 'УВЕРЕННЫЙ ШАГ' : 'БЕРУ ВЫСОТУ'}</span><RichText text={question.question} className="mg-question" /><ChoiceButtons options={question.options} selected={answer} disabled={checked === true} onSelect={i => { setAnswer(i); setChecked(null); }} />{checked !== null && <div role="status" className="mg-feedback"><strong>{checked ? 'Верный шаг!' : 'Посмотрим на правило ещё раз'}</strong><RichText text={question.explanation} /></div>}<div className="mg-actions">{checked === true ? <button className="mg-button" onClick={next}>{step === 2 ? 'На вершину' : 'Следующая остановка'}<ArrowRight size={17} /></button> : <><button className="mg-button" disabled={answer === null} onClick={verify}>Проверить ответ</button><button className="mg-button secondary" onClick={() => { setRoute(null); setAnswer(null); setChecked(null); }}>Выбрать другой путь</button></>}</div></div>}
    </>}
  </GameFrame>;
}
