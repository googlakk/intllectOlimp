import { describe, expect, it } from 'vitest';

import { buildHorizontalMindMapLayout } from './MindMap';

describe('buildHorizontalMindMapLayout', () => {
  it('places every child of a branch in one horizontal lane', () => {
    const layout = buildHorizontalMindMapLayout('Целые числа', [
      { label: 'Сложение', children: ['Одинаковые знаки', 'Разные знаки', 'Проверка'] },
      { label: 'Порядок действий', children: ['Скобки', 'Умножение', 'Сложение'] },
    ]);

    for (const row of layout.rows) {
      expect(row.leaves.every((leaf) => leaf.y === row.branch.y)).toBe(true);
      expect(row.leaves.map((leaf) => leaf.x)).toEqual(
        [...row.leaves.map((leaf) => leaf.x)].sort((a, b) => a - b),
      );
    }
  });

  it('grows horizontally when a branch gets more ideas', () => {
    const compact = buildHorizontalMindMapLayout('Тема', [
      { label: 'Ветвь', children: ['Одна идея'] },
    ]);
    const detailed = buildHorizontalMindMapLayout('Тема', [
      { label: 'Ветвь', children: ['Одна', 'Две', 'Три', 'Четыре', 'Пять'] },
    ]);

    expect(detailed.width).toBeGreaterThan(compact.width);
    expect(detailed.height).toBe(compact.height);
  });
});
