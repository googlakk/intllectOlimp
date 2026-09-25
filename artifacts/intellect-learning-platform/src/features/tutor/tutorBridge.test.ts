import { describe, expect, it, vi } from 'vitest';
import { tutorAttemptProps } from './tutorBridge';

describe('tutorAttemptProps', () => {
  it('привязывает попытку к исходному индексу блока и шагу маршрута', () => {
    const onAttempt = vi.fn();
    const props = tutorAttemptProps('GuidedPractice', { onAttempt }, 7, 3);
    props.onAttempt?.({ value: '18 м/с', outcome: 'wrong_unit', hintsSeen: 1 });
    expect(onAttempt).toHaveBeenCalledWith({ value: '18 м/с', outcome: 'wrong_unit', hintsSeen: 1, blockIndex: 7, stepIndex: 3 });
  });

  it('обрезает длинный ответ до предела API', () => {
    const onAttempt = vi.fn();
    tutorAttemptProps('IndependentProblem', { onAttempt }, 0, 0).onAttempt?.({ value: 'а'.repeat(250), outcome: 'incorrect' });
    expect(onAttempt.mock.calls[0][0].value).toHaveLength(200);
  });

  it('ничего не передаёт без тьютора и для других блоков', () => {
    expect(tutorAttemptProps('GuidedPractice', {}, 0, 0)).toEqual({});
    expect(tutorAttemptProps('MasteryCheck', { onAttempt: vi.fn() }, 0, 0)).toEqual({});
  });
});
