import { describe, expect, it } from 'vitest';
import { answerSample, emptySample, restoreSample } from './sampleModel';
import { physicsLesson } from './physicsContent';
import { historyLesson } from './historyContent';

describe('visual sample progress', () => {
  it('tracks corrections without duplicating solved answers', () => {
    const wrong = answerSample(emptySample(), physicsLesson, 'calculate', 1);
    const right = answerSample(wrong, physicsLesson, 'calculate', 0);
    expect(right.answers.calculate).toEqual({ choice: 0, tries: 2 });
    expect(answerSample(right, physicsLesson, 'calculate', 1)).toBe(right);
  });
  it('rejects invalid choices and unknown questions', () => {
    const state = emptySample();
    for (const [id, choice] of [['missing', 0], ['calculate', -1], ['calculate', 99], ['calculate', NaN]] as const) expect(answerSample(state, physicsLesson, id, choice)).toBe(state);
  });
  it('restores answers and position but isolates each lesson', () => {
    const state = { ...answerSample(emptySample(), physicsLesson, 'calculate', 0), step: 4 };
    expect(restoreSample(JSON.stringify(state), physicsLesson)).toEqual(state);
    expect(restoreSample(JSON.stringify(state), historyLesson).answers).toEqual({});
  });
  it('recovers corrupted saves without awarding results', () => {
    for (const raw of [null, 'broken', '[]', '{"version":2}', '{"version":1,"step":99,"answers":{"calculate":{"choice":99,"tries":1}}}']) expect(restoreSample(raw, physicsLesson)).toEqual(emptySample());
  });
  it('all lesson questions have a valid answer and explanation', () => {
    for (const lesson of [physicsLesson, historyLesson]) {
      expect(lesson.sceneNames).toHaveLength(7);
      expect(Object.keys(lesson.questions)).toHaveLength(3);
      for (const q of Object.values(lesson.questions)) { expect(q.options[q.correct]).toBeTruthy(); expect(q.explanation.length).toBeGreaterThan(30); }
    }
  });
});
