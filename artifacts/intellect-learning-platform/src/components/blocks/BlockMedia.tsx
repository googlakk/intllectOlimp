import type { Block } from '@/lib/api/types';
import { useProtectedMediaUrl } from '@/lib/useProtectedMediaUrl';

/** Блоки, у которых иллюстрация живёт внутри самого блока (content.media). */
export const INLINE_MEDIA_COMPONENTS = new Set([
  'ShortExplanation', 'KeyConcept', 'WorkedExample', 'PredictionLab', 'BranchingScenario',
  'GuidedPractice', 'IndependentProblem', 'Timeline',
]);

type InlineMedia = { kind?: string; url?: string; alt_text?: string; caption?: string };

export function inlineBlockMedia(block: Block): InlineMedia | null {
  if (!INLINE_MEDIA_COMPONENTS.has(block.component)) return null;
  const media = block.content?.media;
  if (!media || typeof media !== 'object') return null;
  const value = media as InlineMedia;
  return value.kind !== 'video' && typeof value.url === 'string' && value.url ? value : null;
}

/** Иллюстрация над содержимым блока: сцена задачи, понятие, ситуация. */
export function BlockMedia({ block }: { block: Block }) {
  const media = inlineBlockMedia(block);
  const image = useProtectedMediaUrl(media?.url);
  if (!media || !image.url) return null;
  return (
    <figure className="mx-auto mb-4 w-fit max-w-full overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      <img
        src={image.url}
        alt={media.alt_text || ''}
        className="block h-auto max-h-[360px] w-auto max-w-full"
        loading="lazy"
        decoding="async"
      />
      {media.caption && <figcaption className="border-t border-border px-4 py-2 text-center text-sm text-muted-foreground">{media.caption}</figcaption>}
    </figure>
  );
}
