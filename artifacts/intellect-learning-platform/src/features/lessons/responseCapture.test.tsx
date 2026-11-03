import { beforeEach, describe, expect, it, vi } from 'vitest';
import { isValidElement, type ReactElement, type ReactNode } from 'react';
import GuidedPractice from '@/components/blocks/GuidedPractice';
import IndependentProblem from '@/components/blocks/IndependentProblem';
import RetrievalCheck from '@/components/blocks/RetrievalCheck';
import MasteryCheck from '@/components/blocks/MasteryCheck';
import SortAndClassify from '@/components/blocks/SortAndClassify';
import LearningPath from '@/features/miniGames/LearningPath';
import type { GameData } from '@/features/miniGames/model';
import { responseKey } from './responseDetails';

// Exercise the component's real submit handlers without introducing a DOM test dependency.
const state = vi.hoisted(() => ({ seeds: [] as unknown[] }));
vi.mock('react', async () => {
  const actual = await vi.importActual<typeof import('react')>('react');
  const useState = (initial: unknown) => [state.seeds.length ? state.seeds.shift() : typeof initial === 'function' ? initial() : initial, vi.fn()];
  const useMemo = (compute: () => unknown) => compute();
  return {
    ...actual,
    default: { ...actual, useState, useMemo },
    useState,
    useMemo,
  };
});

vi.mock('@dnd-kit/core', async () => {
  const actual = await vi.importActual<typeof import('@dnd-kit/core')>('@dnd-kit/core');
  return { ...actual, useSensor: vi.fn(), useSensors: () => [] };
});

type EventProps = { children?: ReactNode; onSubmit?: (event: { preventDefault: () => void }) => void; onClick?: () => void };
function find(node: ReactNode, predicate: (element: ReactElement<EventProps>) => boolean): ReactElement<EventProps> | undefined {
  if (Array.isArray(node)) {
    for (const child of node) {
      const match = find(child, predicate);
      if (match) return match;
    }
    return;
  }
  if (!isValidElement<EventProps>(node)) return;
  return predicate(node) ? node : find(node.props.children, predicate);
}

describe('submitted lesson responses', () => {
  beforeEach(() => { state.seeds = []; });

  it('keeps original block and individual question keys separate', () => {
    expect(responseKey(12)).toBe('12');
    expect(responseKey(12, 0)).toBe('12_q0');
    expect(responseKey(12, 1)).toBe('12_q1');
    expect(responseKey(1, 2)).not.toBe(responseKey(12));
  });

  it('captures the just-clicked option, before grading, without waiting for a state update', () => {
    const events: string[] = [];
    const onResponse = vi.fn(() => events.push('response'));
    const tree = RetrievalCheck({ question: 'Столица?', options: ['Бишкек', 'Ош'], correct_answer: 'Бишкек', explanation: '', onResponse, onAnswer: () => events.push('grade') });
    const option = find(tree, element => element.type === 'button' && typeof element.props.onClick === 'function');
    expect(option).toBeDefined();
    option!.props.onClick!();
    expect(onResponse).toHaveBeenCalledWith({ value: 'Бишкек', outcome: 'correct' });
    expect(events).toEqual(['response', 'grade']);
  });

  it.each(['guided', 'independent'])('saves a wrong-unit response in %s practice without grading or consuming an attempt', (kind) => {
    state.seeds = kind === 'guided' ? ['5 см', 'idle', 0] : ['5 см', 'idle', 0];
    const onResponse = vi.fn(), onAnswer = vi.fn();
    const common = { question: 'Длина в метрах', correct_answer: '5', answer_unit: 'м', explanation: '', onResponse, onAnswer };
    const tree = kind === 'guided'
      ? GuidedPractice({ ...common, hints: [], input_type: 'numeric' })
      : IndependentProblem({ ...common, type: 'numeric', difficulty: 'basic' });
    find(tree, element => element.type === 'form')!.props.onSubmit!({ preventDefault: vi.fn() });
    expect(onResponse).toHaveBeenCalledWith({ value: '5 см', outcome: 'wrong_unit' });
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it('captures a mastery question with its own index, including a wrong unit before the early return', () => {
    const onResponse = vi.fn(), onAnswer = vi.fn();
    const question = { question: 'Расстояние?', type: 'numeric' as const, correct_answer: '5', answer_unit: 'м', explanation: '', dimension: 'length' };
    // The submit button reads currentValue, seeded as the value entered into question 2.
    state.seeds = [1, {}, false, '5 см', false];
    const filled = MasteryCheck({ questions: [question, question], onResponse, onAnswer });
    const button = find(filled, element => element.type === 'button' && typeof element.props.onClick === 'function');
    button!.props.onClick!();
    expect(onResponse).toHaveBeenCalledWith({ value: '5 см', outcome: 'wrong_unit', questionIndex: 1 });
    expect(onAnswer).not.toHaveBeenCalled();
  });

  it('captures labels of the actual submitted classification, including an incorrect placement', () => {
    state.seeds = [{ cat: 'plants', oak: 'animals' }, 'idle', null];
    const onResponse = vi.fn(), onAnswer = vi.fn();
    const tree = SortAndClassify({
      title: 'Классификация', instruction: '', explanation: '',
      items: [{ id: 'cat', label: 'Кошка', correct_group: 'animals' }, { id: 'oak', label: 'Дуб', correct_group: 'plants' }],
      groups: [{ id: 'animals', label: 'Животные' }, { id: 'plants', label: 'Растения' }],
      onResponse, onAnswer,
    });
    const button = find(tree, element => element.props.children === 'Проверить классификацию');
    button!.props.onClick!();
    expect(onResponse).toHaveBeenCalledWith({ value: 'Кошка → Растения\nДуб → Животные', outcome: 'incorrect' });
    expect(onAnswer).toHaveBeenCalledWith(false);
  });

  it('keeps a learning-path checkpoint attached to the chosen variant and actual option', () => {
    const choice = { question: 'Выберите ответ', options: ['А', 'Б'], correct_index: 1, explanation: '' };
    const data: GameData['LearningPath'] = {
      title: 'Маршрут', instruction: 'Пройди маршрут', takeaway: 'Итог', duration_minutes: 3,
      checkpoints: Array.from({ length: 3 }, (_, index) => ({ label: `Этап ${index + 1}`, support: { ...choice, explanation: 'Пояснение' }, challenge: { ...choice, explanation: 'Пояснение' } })),
    };
    const onResponse = vi.fn(), onAnswer = vi.fn();
    const outer = LearningPath({ ...data, onResponse, onAnswer });
    // Open checkpoint 2 on its challenge path and submit option A (the wrong one).
    state.seeds = [1, 'challenge', 0, null, ['support']];
    const Session = outer.type as (props: typeof outer.props) => ReactNode;
    const tree = Session(outer.props);
    find(tree, element => element.props.children === 'Проверить ответ')!.props.onClick!();
    expect(onResponse).toHaveBeenCalledWith({ value: 'А', outcome: 'incorrect', questionIndex: 1, variant: 'challenge' });
    expect(onAnswer).toHaveBeenCalledWith(false);
  });
});
