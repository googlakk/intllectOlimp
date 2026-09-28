export type GameBase = { title: string; instruction: string; takeaway: string; duration_minutes: number };
export type Choice = { question: string; options: string[]; correct_index: number; explanation: string };
export type GameData = {
  BossRaid: GameBase & { rounds: { question: string; answer: string; explanation: string }[] };
  CodeVault: GameBase & { clues: (Choice & { label: string; digit: number })[] };
  KnowledgeAuction: GameBase & { statements: { text: string; is_true: boolean; explanation: string }[] };
  WordRelay: GameBase & { cards: { term: string; forbidden: string[]; hint: string }[] };
  PuzzleAssembly: GameBase & { slots: { id: string; label: string }[]; pieces: { id: string; text: string; slot_id: string }[] };
  ErrorHunt: GameBase & { lines: { text: string; is_error: boolean; fixes: string[]; correct_index: number | null; explanation: string }[] };
  LearningPath: GameBase & { checkpoints: { label: string; support: Choice; challenge: Choice }[] };
};
export type GameName = keyof GameData;
export type GameProps = Record<string, unknown> & { onAnswer?: (correct: boolean) => void };
export const GAME_NAMES: GameName[] = ['BossRaid', 'CodeVault', 'KnowledgeAuction', 'WordRelay', 'PuzzleAssembly', 'ErrorHunt', 'LearningPath'];
export const GAME_IDS = ['boss-raid', 'code-vault', 'knowledge-auction', 'word-relay', 'puzzle-assembly', 'error-hunt', 'learning-path'];
const object = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const text = (v: unknown): v is string => typeof v === 'string' && v.trim().length > 0;
const count = (v: unknown, lo: number, hi: number): v is unknown[] => Array.isArray(v) && v.length >= lo && v.length <= hi;
const strings = (v: unknown, lo: number, hi: number): v is string[] => count(v, lo, hi) && v.every(text) && new Set(v.map(x => x.trim().toLowerCase())).size === v.length;
const index = (n: unknown, len: number) => typeof n === 'number' && Number.isInteger(n) && n >= 0 && n < len;
const choice = (v: unknown) => object(v) && text(v.question) && text(v.explanation) && strings(v.options, 2, 4) && index(v.correct_index, v.options.length);

/** Fail closed for malformed stored/generated content before creating a game session. */
export function readGame<N extends GameName>(name: N, raw: unknown): GameData[N] | null {
  if (!object(raw) || !text(raw.title) || !text(raw.instruction) || !text(raw.takeaway) || !Number.isInteger(raw.duration_minutes) || Number(raw.duration_minutes) < 3 || Number(raw.duration_minutes) > 7) return null;
  let valid = false;
  switch (name) {
    case 'BossRaid': valid = count(raw.rounds, 3, 5) && raw.rounds.every(v => object(v) && text(v.question) && text(v.answer) && text(v.explanation)); break;
    case 'CodeVault': valid = count(raw.clues, 3, 5) && raw.clues.every(v => object(v) && choice(v) && text(v.label) && index(v.digit, 10)); break;
    case 'KnowledgeAuction': valid = count(raw.statements, 3, 5) && raw.statements.every(v => object(v) && text(v.text) && typeof v.is_true === 'boolean' && text(v.explanation)) && raw.statements.some(v => object(v) && v.is_true === true) && raw.statements.some(v => object(v) && v.is_true === false); break;
    case 'WordRelay': valid = count(raw.cards, 4, 8) && raw.cards.every(v => object(v) && text(v.term) && text(v.hint) && strings(v.forbidden, 3, 5) && !v.forbidden.some(w => w.toLowerCase().trim() === String(v.term).toLowerCase().trim())); break;
    case 'PuzzleAssembly': {
      if (!count(raw.slots, 4, 8) || !raw.slots.every(v => object(v) && text(v.id) && text(v.label)) || !count(raw.pieces, raw.slots.length, raw.slots.length) || !raw.pieces.every(v => object(v) && text(v.id) && text(v.text) && text(v.slot_id))) break;
      const slots = raw.slots as { id: string }[], pieces = raw.pieces as { id: string; slot_id: string }[];
      valid = new Set(slots.map(v => v.id)).size === slots.length && new Set(pieces.map(v => v.id)).size === pieces.length && new Set(pieces.map(v => v.slot_id)).size === slots.length && pieces.every(v => slots.some(s => s.id === v.slot_id)); break;
    }
    case 'ErrorHunt': valid = count(raw.lines, 3, 6) && raw.lines.every(v => object(v) && text(v.text) && text(v.explanation) && typeof v.is_error === 'boolean' && (v.is_error ? strings(v.fixes, 2, 4) && index(v.correct_index, v.fixes.length) : Array.isArray(v.fixes) && v.fixes.length === 0 && v.correct_index === null)) && raw.lines.some(v => object(v) && v.is_error === true) && raw.lines.some(v => object(v) && v.is_error === false); break;
    case 'LearningPath': valid = count(raw.checkpoints, 3, 3) && raw.checkpoints.every(v => object(v) && text(v.label) && choice(v.support) && choice(v.challenge)); break;
  }
  return valid ? raw as unknown as GameData[N] : null;
}

export const TEAM_NAMES = ['Комета', 'Орбита', 'Пульсар', 'Спутник', 'Зенит', 'Вектор'];
export function settleAuction(coins: number[], scores: number[], bids: number[], approved: boolean[], truth: boolean) {
  const safeBids = coins.map((balance, i) => Math.min(balance, Math.max(0, Math.floor(bids[i] || 0))));
  return { coins: coins.map((n, i) => n - safeBids[i]), scores: scores.map((n, i) => n + (truth && approved[i] ? safeBids[i] * 2 : 0)) };
}

export function puzzleCorrect(data: GameData['PuzzleAssembly'], placements: Record<string, string>) {
  return data.slots.every(slot => data.pieces.some(piece => piece.id === placements[slot.id] && piece.slot_id === slot.id));
}

export function repairsCorrect(data: GameData['ErrorHunt'], answers: Record<number, number>) {
  return data.lines.every((line, i) => answers[i] === (line.is_error ? line.correct_index : -1));
}
