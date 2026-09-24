import { describe, expect, it } from 'vitest';
import type { LessonScene } from '@/lib/api/types';
import { avatarCueForBeat, defaultBeatId } from './lessonExperience';

const scene: LessonScene = {
  id: 'scene-1',
  purpose: 'explain',
  title: 'Презентация',
  objective_ids: ['o1'],
  block: { component: 'Presentation', content: {} },
  teaching_beats: [
    { id: 'slide-1', objective_ids: ['o1'], title: 'Первый', avatar_cue_ids: ['cue-1'], media_slot_ids: [] },
    { id: 'slide-2', objective_ids: ['o1'], title: 'Второй', avatar_cue_ids: ['cue-2'], media_slot_ids: [] },
  ],
  avatar_cues: [
    { id: 'cue-1', beat_id: 'slide-1', phase: 'explain', script: 'Первое объяснение', trigger: 'scene_start', fallback_text: 'Первое объяснение' },
    { id: 'cue-2', beat_id: 'slide-2', phase: 'explain', script: 'Второе объяснение', trigger: 'scene_start', fallback_text: 'Второе объяснение' },
  ],
  completion_rule: 'viewed',
};

describe('lesson beat orchestration', () => {
  it('selects the first visible teaching beat by default', () => {
    expect(defaultBeatId(scene)).toBe('slide-1');
  });

  it('selects the avatar cue anchored to the active slide', () => {
    expect(avatarCueForBeat(scene, 'slide-2')?.id).toBe('cue-2');
  });

  it('falls back for legacy scenes without beat identifiers', () => {
    const legacy = { ...scene, teaching_beats: undefined, avatar_cues: [{
      id: 'legacy', phase: 'explain', script: 'Объяснение', trigger: 'scene_start', fallback_text: 'Объяснение',
    }] };
    expect(avatarCueForBeat(legacy, undefined)?.id).toBe('legacy');
  });
});
