import { ArrowRight, CheckCircle2, Sparkles } from 'lucide-react';
import { RichText } from '@/components/blocks/RichText';
import { useProtectedMediaUrl } from '@/lib/useProtectedMediaUrl';
import type { LessonIntro } from './lessonIntro';

/** Первая страница урока: заинтересовать до первого вопроса. */
export function LessonTitlePage({ intro, onStart }: { intro: LessonIntro; onStart: () => void }) {
  const image = useProtectedMediaUrl(intro.imageUrl);
  const hasImage = Boolean(image.url);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <section
          aria-label="Титульная страница урока"
          className={`mx-auto grid max-w-6xl items-center gap-8 py-4 sm:py-8 lg:gap-12 ${hasImage ? 'lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]' : 'max-w-3xl text-center'}`}
        >
          <div className="min-w-0">
            {intro.kicker && (
              <p className={`flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-primary ${hasImage ? '' : 'justify-center'}`}>
                <Sparkles className="h-4 w-4" aria-hidden="true" /> {intro.kicker}
              </p>
            )}
            <h1 className="mt-4 text-4xl font-bold leading-[1.08] tracking-tight text-foreground sm:text-5xl lg:text-6xl">
              <RichText text={intro.title} inline />
              {intro.accent && <span className="mt-1 block text-primary"><RichText text={intro.accent} inline /></span>}
            </h1>
            {intro.hook && (
              <div className={`mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground sm:text-xl ${hasImage ? '' : 'mx-auto'}`}>
                <RichText text={intro.hook} />
              </div>
            )}
            {intro.promise.length > 0 && (
              <div className={`mt-7 max-w-xl rounded-2xl border border-border bg-card p-4 text-left shadow-sm ${hasImage ? '' : 'mx-auto'}`}>
                <p className="text-sm font-bold text-foreground">Что ты сможешь после урока</p>
                <ul className="mt-2 space-y-2">
                  {intro.promise.map((item) => (
                    <li key={item} className="flex gap-2 text-sm leading-relaxed text-foreground">
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p className="mt-5 text-sm text-muted-foreground">{intro.meta.join(' · ')}</p>
          </div>
          {hasImage && (
            <figure className="overflow-hidden rounded-[2rem] border border-border bg-card shadow-md">
              <img src={image.url} alt="" className="h-auto max-h-[62vh] w-full object-contain" fetchPriority="high" />
            </figure>
          )}
        </section>
      </div>
      <div className="flex shrink-0 justify-end border-t border-border/60 pt-3 pr-20 sm:pr-0">
        <button
          type="button"
          onClick={onStart}
          className="flex w-[240px] items-center justify-center gap-2 rounded-xl bg-primary px-8 py-3.5 font-bold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
        >
          {intro.cta} <ArrowRight className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
