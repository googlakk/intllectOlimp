import type { SaveProgressInput } from '@/lib/api';

export const IN_PROGRESS_SAVE_DEBOUNCE_MS = 500;

export function shouldSaveProgressImmediately(status: SaveProgressInput['status']) {
  return status === 'completed';
}

export function coalesceProgressSave(
  _previous: SaveProgressInput | null,
  next: SaveProgressInput,
): SaveProgressInput {
  return next;
}
