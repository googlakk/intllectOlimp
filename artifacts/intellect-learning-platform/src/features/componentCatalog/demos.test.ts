import { describe, expect, it } from 'vitest';
import { componentDemos } from './demos';

describe('component demos', () => {
  it('provides a renderable block and guidance text for each demo', () => {
    for (const [id, demo] of Object.entries(componentDemos)) {
      expect(id.length).toBeGreaterThan(0);
      expect(demo.usage.length).toBeGreaterThan(0);
      expect(demo.interaction.length).toBeGreaterThan(0);
      expect(demo.block.component.length).toBeGreaterThan(0);
      expect(typeof demo.block.content).toBe('object');
    }
  });

  it('covers the catalog ids that are shown in teacher demos', () => {
    expect(Object.keys(componentDemos).sort()).toEqual([
      'argument-builder',
      'guided-practice',
      'illustration',
      'independent-problem',
      'interactive-graph',
      'key-concept',
      'mastery-check',
      'mind-map',
      'presentation',
      'reflection',
      'retrieval-check',
      'short-explanation',
      'text-evidence-picker',
      'timeline',
      'worked-example',
    ]);
  });
});
