import { useState } from 'react';
import { ArrowLeft, Swords, KeyRound, Gavel, Mic2, Puzzle, ScanLine, Mountain } from 'lucide-react';
import { Link } from 'wouter';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import { miniGameDemos } from './demos';

const choices = [
  { id: 'boss-raid', title: 'Одолей босса', icon: Swords, group: true, color: '#7771c9' },
  { id: 'code-vault', title: 'Секретный код', icon: KeyRound, group: true, color: '#227864' },
  { id: 'knowledge-auction', title: 'Аукцион', icon: Gavel, group: true, color: '#a87b25' },
  { id: 'word-relay', title: 'Объясни иначе', icon: Mic2, group: true, color: '#bd4834' },
  { id: 'puzzle-assembly', title: 'Собери целое', icon: Puzzle, group: true, color: '#256e7b' },
  { id: 'error-hunt', title: 'Почини решение', icon: ScanLine, group: false, color: '#375ccd' },
  { id: 'learning-path', title: 'Мой маршрут', icon: Mountain, group: false, color: '#487e55' },
];
export default function MiniGamesShowcase() {
  const [active, setActive] = useState(choices[0].id);
  return <main className="min-h-screen bg-[#f5f4f0] px-4 py-8 text-[#263530] sm:px-8">
    <div className="mx-auto max-w-6xl">
      <Link href="/dashboard/components" className="inline-flex items-center gap-2 text-sm font-semibold text-[#57635c]"><ArrowLeft size={16} /> В библиотеку компонентов</Link>
      <header className="mb-8 mt-8 max-w-2xl"><p className="text-xs font-bold uppercase tracking-[.22em] text-[#69756d]">Intellect · игровая мастерская</p><h1 className="mt-3 text-4xl font-extrabold tracking-tight sm:text-5xl">Маленькая игра.<br />Большое открытие.</h1><p className="mt-4 text-base leading-relaxed text-[#69756d]">5 групповых и 2 индивидуальные мини-игры на 3–7 минут. Здесь — демонстрационные задания. В уроке содержание готовится по вашей теме и учебнику.</p></header>
      <div className="grid items-start gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
        <nav aria-label="Выбрать мини-игру" className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:sticky lg:top-6 lg:grid-cols-1">{choices.map(({ id, title, icon: Icon, group, color }, i) => <button key={id} aria-pressed={active === id} onClick={() => setActive(id)} className={`flex min-h-20 min-w-0 items-center gap-3 rounded-2xl border p-3 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 ${active === id ? 'border-[#263530] bg-white shadow-sm' : 'border-transparent bg-[#eaeae3] hover:bg-white'}`}><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-white" style={{ background: color }}><Icon size={20} /></span><span className="min-w-0"><span className="block text-[10px] font-bold uppercase tracking-wider text-[#69756d]">0{i + 1} · {group ? 'Группа' : 'Самостоятельно'}</span><span className="mt-1 block text-sm font-bold leading-tight">{title}</span></span></button>)}</nav>
        <div className="min-w-0" role="region" aria-label="Живая мини-игра"><BlockRenderer key={active} blocks={[miniGameDemos[active].block]} /><p className="mt-4 text-sm text-[#69756d]">{miniGameDemos[active].interaction}</p></div>
      </div>
    </div>
  </main>;
}
