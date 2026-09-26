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
      'argument-map',
      'branching-scenario',
      'cause-effect-map',
      'chronology-line',
      'code-blocks-lab',
      'data-investigation',
      'function-explorer',
      'generated-media',
      'guided-practice',
      'hotspot-investigation',
      'illustration',
      'independent-problem',
      'interactive-graph',
      'key-concept',
      'mastery-check',
      'mind-map',
      'misconception-debugger',
      'physics-sandbox',
      'prediction-lab',
      'presentation',
      'process-builder',
      'reflection',
      'retrieval-check',
      'short-explanation',
      'sort-and-classify',
      'step-solver',
      'text-evidence-picker',
      'timeline',
      'worked-example',
    ]);
  });
});
