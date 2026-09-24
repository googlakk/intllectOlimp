import type { Block } from '@/lib/api/types';

export type MediaPlacementTarget = {
  blockIndex: number;
  slideIndex?: number;
  sceneId?: string;
  beatId?: string;
  slideId?: string;
  mediaSlotId?: string;
  heading?: string;
  learningGoal?: string;
  pedagogicalRole?: string;
  visualIntent?: string;
  successCheck?: string;
  requiredVisuals?: string[];
  avoidedVisuals?: string[];
};

export type PlacedLessonMedia = {
  kind: 'image' | 'video';
  url: string;
  poster_url?: string;
  alt_text: string;
  caption: string;
  prompt?: string;
  model?: string;
  job_id?: string;
  generation_id?: string;
};

export function placeGeneratedMedia(
  blocks: Block[],
  target: MediaPlacementTarget,
  media: PlacedLessonMedia,
  topicName: string,
): Block[] {
  const sourceBlock = blocks[target.blockIndex];
  if (!sourceBlock) return blocks;
  const nextBlocks = [...blocks];

  if (sourceBlock.component === 'Presentation' && target.slideIndex !== undefined) {
    const slides = Array.isArray(sourceBlock.content.slides)
      ? sourceBlock.content.slides.map((slide) => ({ ...(slide as Record<string, unknown>) }))
      : [];
    const slide = slides[target.slideIndex];
    if (!slide) return blocks;
    const slideId = typeof slide.id === 'string' ? slide.id : `slide-${target.slideIndex + 1}`;
    const mediaSlotId = target.mediaSlotId || `media-${slideId}`;
    slide.id = slideId;
    slide.media_slot = {
      ...(slide.media_slot && typeof slide.media_slot === 'object' ? slide.media_slot as Record<string, unknown> : {}),
      id: mediaSlotId,
      role: target.pedagogicalRole || 'clarify',
      placement: 'slide_visual',
      learning_purpose: target.learningGoal || target.heading || topicName,
      must_show: target.requiredVisuals || [],
      must_not_show: target.avoidedVisuals || [],
    };
    slide.media = {
      ...media,
      media_slot_id: mediaSlotId,
      pedagogical_role: target.pedagogicalRole || 'clarify',
    };
    slides[target.slideIndex] = slide;
    nextBlocks[target.blockIndex] = {
      ...sourceBlock,
      content: { ...sourceBlock.content, slides },
    };
    return nextBlocks;
  }

  const anchorId = `block-${target.blockIndex + 1}`;
  const anchoredBlock: Block = {
    component: 'GeneratedMedia',
    content: {
      title: media.kind === 'video'
        ? `Видео к шагу: ${target.heading || topicName}`
        : `Визуализация к шагу: ${target.heading || topicName}`,
      description: target.learningGoal || `Визуальное объяснение темы ${topicName}`,
      media_kind: media.kind,
      url: media.url,
      poster_url: media.poster_url,
      alt_text: media.alt_text,
      caption: media.caption,
      pedagogical_role: target.pedagogicalRole || 'clarify',
      visual_intent: target.visualIntent,
      success_check: target.successCheck,
      anchor: {
        scene_id: target.sceneId,
        block_id: anchorId,
        beat_id: target.beatId,
        placement: 'after_block',
      },
      prompt: media.prompt,
      model: media.model,
      job_id: media.job_id,
      generation_id: media.generation_id,
    },
  };
  const next = nextBlocks[target.blockIndex + 1];
  const nextAnchor = next?.content?.anchor as Record<string, unknown> | undefined;
  if (next?.component === 'GeneratedMedia' && nextAnchor?.block_id === anchorId) {
    nextBlocks[target.blockIndex + 1] = anchoredBlock;
  } else {
    nextBlocks.splice(target.blockIndex + 1, 0, anchoredBlock);
  }
  return nextBlocks;
}

export function replaceGeneratedMediaJob(
  blocks: Block[],
  jobId: string,
  media: PlacedLessonMedia,
): Block[] {
  let changed = false;
  const nextBlocks = blocks.map((block) => {
    if (block.component === 'GeneratedMedia' && block.content.job_id === jobId) {
      changed = true;
      return { ...block, content: { ...block.content, ...media } };
    }
    if (block.component !== 'Presentation' || !Array.isArray(block.content.slides)) return block;
    let slidesChanged = false;
    const slides = block.content.slides.map((rawSlide) => {
      if (!rawSlide || typeof rawSlide !== 'object') return rawSlide;
      const slide = rawSlide as Record<string, unknown>;
      const currentMedia = slide.media && typeof slide.media === 'object'
        ? slide.media as Record<string, unknown>
        : undefined;
      if (currentMedia?.job_id !== jobId) return rawSlide;
      changed = true;
      slidesChanged = true;
      return { ...slide, media: { ...currentMedia, ...media } };
    });
    return slidesChanged ? { ...block, content: { ...block.content, slides } } : block;
  });
  return changed ? nextBlocks : blocks;
}
