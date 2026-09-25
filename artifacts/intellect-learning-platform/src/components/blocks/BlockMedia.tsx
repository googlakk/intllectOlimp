import { useState, type ReactNode } from 'react';
import { Maximize2 } from 'lucide-react';
import type { Block } from '@/lib/api/types';
import { useProtectedMediaUrl } from '@/lib/useProtectedMediaUrl';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';

/** Блоки, у которых иллюстрация живёт внутри самого блока (content.media). */
export const INLINE_MEDIA_COMPONENTS = new Set([
  'ShortExplanation', 'KeyConcept', 'WorkedExample', 'PredictionLab', 'BranchingScenario',
  'GuidedPractice', 'IndependentProblem', 'Timeline',
]);

/** Блоки, которые сами ставят картинку в нужное место своей вёрстки. */
export const SELF_MEDIA_COMPONENTS = new Set([
  'ShortExplanation', 'KeyConcept', 'Timeline', 'WorkedExample', 'GuidedPractice', 'IndependentProblem',
  'PredictionLab', 'BranchingScenario',
]);

export type InlineMedia = { kind?: string; url?: string; alt_text?: string; caption?: string };

/** Картинка из content.media, если она есть и это не видео. */
export function blockImage(media: unknown): InlineMedia | null {
  if (!media || typeof media !== 'object') return null;
  const value = media as InlineMedia;
  return value.kind !== 'video' && typeof value.url === 'string' && value.url ? value : null;
}

export function inlineBlockMedia(block: Block): InlineMedia | null {
  if (!INLINE_MEDIA_COMPONENTS.has(block.component)) return null;
  return blockImage(block.content?.media);
}

type Variant = 'top' | 'side' | 'thumb';

const FRAME: Record<Variant, string> = {
  top: 'mx-auto w-fit max-w-full',
  side: 'w-full',
  thumb: 'w-24 shrink-0 sm:w-32',
};
const IMAGE: Record<Variant, string> = {
  top: 'h-auto max-h-[360px] w-auto max-w-full',
  side: 'h-auto w-full',
  thumb: 'aspect-[4/3] w-full object-cover',
};

/**
 * Иллюстрация внутри блока. Нажатие открывает её крупно: на картинках
 * бывают подписи и детали, которые в узкой колонке не разглядеть.
 */
export function BlockImage({ media, variant = 'top', className = '' }: { media: unknown; variant?: Variant; className?: string }) {
  const value = blockImage(media);
  const image = useProtectedMediaUrl(value?.url);
  const [open, setOpen] = useState(false);
  if (!value || !image.url) return null;
  const alt = value.alt_text || '';
  return (
    <figure className={`${FRAME[variant]} ${className}`}>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="group relative block w-full overflow-hidden rounded-xl border border-border bg-muted/30 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        aria-label="Открыть иллюстрацию крупно"
      >
        <img src={image.url} alt={alt} className={`block ${IMAGE[variant]}`} loading="lazy" decoding="async" />
        <span className="absolute bottom-1.5 right-1.5 flex h-8 w-8 items-center justify-center rounded-full bg-background/85 text-foreground opacity-0 shadow-sm transition group-hover:opacity-100 group-focus-visible:opacity-100">
          <Maximize2 className="h-4 w-4" />
        </span>
      </button>
      {value.caption && <figcaption className="mt-2 text-center text-sm text-muted-foreground">{value.caption}</figcaption>}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-5xl p-3 pt-12 sm:p-4 sm:pt-12">
          <DialogTitle className="sr-only">{alt || 'Иллюстрация'}</DialogTitle>
          <img src={image.url} alt={alt} className="mx-auto max-h-[80vh] w-auto max-w-full rounded-lg" />
          {value.caption && <p className="text-center text-sm text-muted-foreground">{value.caption}</p>}
        </DialogContent>
      </Dialog>
    </figure>
  );
}

/**
 * Условие задачи со сценой: картинка слева от текста, на телефоне — над ним.
 * Ученик сначала видит ситуацию, потом читает, что в ней нужно найти.
 */
export function TaskCondition({ media, className = '', children }: { media: unknown; className?: string; children: ReactNode }) {
  const hasImage = Boolean(blockImage(media));
  return (
    <div className={`${className} ${hasImage ? 'grid gap-4 md:grid-cols-[minmax(0,38%)_minmax(0,1fr)] md:items-center' : ''}`}>
      {hasImage && <BlockImage media={media} variant="side" />}
      <div className="min-w-0 whitespace-pre-wrap">{children}</div>
    </div>
  );
}

/** Картинка над блоком для тех, кто ещё не ставит её сам. */
export function BlockMedia({ block }: { block: Block }) {
  if (SELF_MEDIA_COMPONENTS.has(block.component)) return null;
  const media = inlineBlockMedia(block);
  if (!media) return null;
  return <BlockImage media={media} className="mb-4" />;
}
