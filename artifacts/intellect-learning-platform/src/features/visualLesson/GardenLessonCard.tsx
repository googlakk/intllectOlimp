import { ArrowUpRight } from 'lucide-react';
import { Link } from 'wouter';

const samples = [
  { slug: 'square-roots', subject: 'Математика', title: 'Квадратный сад', description: 'Построй квадрат и открой смысл корня.', image: 'square-garden.png', color: '#244434' },
  { slug: 'density', subject: 'Физика', title: 'Мастерская невидимого', description: 'Исследуй массу, объём и плотность.', image: 'density-workshop.png', color: '#173d44' },
  { slug: 'silk-road', subject: 'История', title: 'Один день на Шёлковом пути', description: 'Открой связи в хозяйстве Караханидов.', image: 'karakhanid-city.png', color: '#493326' },
];

export function GardenLessonCard() {
  return <section aria-label="Образцовые визуальные уроки"><div className="mb-4 flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-lg font-bold">Уроки, в которых можно исследовать</h2><p className="text-xs text-muted-foreground">Образцы · 7 класс · прогресс на устройстве</p></div><div className="grid gap-4 md:grid-cols-3">{samples.map(sample => <Link key={sample.slug} href={`/visual/${sample.slug}`} className="group overflow-hidden rounded-2xl text-white shadow-sm transition-shadow hover:shadow-lg focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary" style={{ backgroundColor: sample.color }}><img className="aspect-[1.9] w-full object-cover transition-transform duration-300 motion-safe:group-hover:scale-[1.02]" src={`${import.meta.env.BASE_URL}images/lessons/${sample.image}`} alt="" loading="lazy" /><div className="p-5"><p className="mb-2 text-xs font-semibold uppercase tracking-wider opacity-75">{sample.subject}</p><h3 className="flex items-start justify-between gap-3 text-lg font-bold">{sample.title}<ArrowUpRight size={20} className="shrink-0" /></h3><p className="mt-2 text-sm opacity-85">{sample.description}</p></div></Link>)}</div></section>;
}
