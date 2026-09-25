import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Block } from '@/lib/api/types';
import { IdleTimer } from './idleTimer';
import { isRepeatAttempt, isTutorLocked, resolveTheoryStep, sessionToMessages } from './tutorRules';

const block = (component: string, content: Record<string, unknown> = {}) => ({ component, content }) as unknown as Block;

describe('resolveTheoryStep', () => {
  const route = [0, 2, 3, 5];

  it('переводит исходный индекс в шаг маршрута — только назад и только к открытому', () => {
    expect(resolveTheoryStep({ type: 'open_theory', target_block_index: 2 }, route, 3, 3)).toBe(1);
    expect(resolveTheoryStep({ type: 'open_theory', target_block_index: 5 }, route, 2, 3)).toBeNull();
    expect(resolveTheoryStep({ type: 'open_theory', target_block_index: 3 }, route, 2, 3)).toBeNull();
    expect(resolveTheoryStep({ type: 'open_theory', target_block_index: 1 }, route, 3, 3)).toBeNull();
    expect(resolveTheoryStep({ type: 'call_teacher' }, route, 3, 3)).toBeNull();
    expect(resolveTheoryStep(null, route, 3, 3)).toBeNull();
  });
});

describe('isTutorLocked', () => {
  it('молчит на итоговых заданиях', () => {
    expect(isTutorLocked(block('MasteryCheck'))).toBe(true);
    expect(isTutorLocked(block('GuidedPractice', { evidence_stage: 'assessment' }))).toBe(true);
    expect(isTutorLocked(block('GuidedPractice'))).toBe(false);
    expect(isTutorLocked(undefined)).toBe(false);
  });
});

describe('isRepeatAttempt', () => {
  const attempt = { blockIndex: 2, stepIndex: 1, value: '72', outcome: 'incorrect' as const };
  it('повтор того же ответа не считается новой попыткой', () => {
    expect(isRepeatAttempt(null, attempt)).toBe(false);
    expect(isRepeatAttempt(attempt, { ...attempt })).toBe(true);
    expect(isRepeatAttempt(attempt, { ...attempt, value: '18' })).toBe(false);
    expect(isRepeatAttempt(attempt, { ...attempt, blockIndex: 4 })).toBe(false);
  });
});

describe('sessionToMessages', () => {
  it('восстанавливает реплики по порядку и пропускает молчание', () => {
    const turns = [
      { id: 1, block_index: 2, question_index: null, event: 'message' as const, student_text: 'не понимаю', reply: 'Что дано?', source: 'llm' as const, hint_level: null },
      { id: 2, block_index: 2, question_index: null, event: 'answer_submitted' as const, student_text: null, reply: '', source: 'silent' as const, hint_level: null },
    ];
    expect(sessionToMessages(turns).map((message) => `${message.role}:${message.text}`)).toEqual(['student:не понимаю', 'tutor:Что дано?']);
  });
});

describe('IdleTimer', () => {
  afterEach(() => vi.useRealTimers());

  it('срабатывает один раз за шаг и сбрасывается действием ученика', () => {
    vi.useFakeTimers();
    const onIdle = vi.fn();
    const timer = new IdleTimer(60_000, onIdle);
    timer.reset(true);
    vi.advanceTimersByTime(59_000);
    timer.reset();
    vi.advanceTimersByTime(59_000);
    expect(onIdle).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1_000);
    expect(onIdle).toHaveBeenCalledTimes(1);
    timer.reset();
    vi.advanceTimersByTime(120_000);
    expect(onIdle).toHaveBeenCalledTimes(1);
    timer.reset(true);
    vi.advanceTimersByTime(60_000);
    expect(onIdle).toHaveBeenCalledTimes(2);
    timer.stop();
  });
});
