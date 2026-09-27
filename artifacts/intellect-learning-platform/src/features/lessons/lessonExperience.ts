import type { AvatarCue, LessonDocument, LessonEpisode, LessonScene } from '@/lib/api/types';

export type LessonPosition = {
  episode: LessonEpisode;
  episodeIndex: number;
  scene: LessonScene;
  sceneIndex: number;
};

export function lessonPositionForBlock(
  document: LessonDocument | undefined,
  originalBlockIndex: number | undefined,
): LessonPosition | null {
  if (!document || originalBlockIndex === undefined) return null;
  for (let episodeIndex = 0; episodeIndex < document.episodes.length; episodeIndex += 1) {
    const episode = document.episodes[episodeIndex];
    const sceneIndex = episode.scenes.findIndex((scene) => scene.original_block_index === originalBlockIndex);
    if (sceneIndex >= 0) {
      return { episode, episodeIndex, scene: episode.scenes[sceneIndex], sceneIndex };
    }
  }
  return null;
}

export function defaultBeatId(scene: LessonScene | undefined): string | undefined {
  return scene?.teaching_beats?.[0]?.id || scene?.avatar_cues?.[0]?.beat_id || scene?.id;
}

export function avatarCueForBeat(
  scene: LessonScene | undefined,
  beatId: string | undefined,
): AvatarCue | undefined {
  if (!scene) return undefined;
  const beatCue = beatId
    ? scene.avatar_cues.find((cue) => cue.beat_id === beatId || cue.slide_id === beatId)
    : undefined;
  return beatCue
    || scene.avatar_cues.find((cue) => cue.trigger === 'scene_start' && !cue.beat_id)
    || scene.avatar_cues[0];
}

