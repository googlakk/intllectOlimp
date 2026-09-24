import { describe, expect, it } from 'vitest';
import type { ComponentRegistryEntry, ComponentSchema } from '@/lib/api/types';
import {
  categoryLabel,
  categoryStyle,
  filterComponents,
  formatSchemaType,
  subjectLabel,
} from './model';

const schema: ComponentSchema = {
  type: 'object',
  properties: {
    answer: { type: 'string' },
  },
};

const components: ComponentRegistryEntry[] = [
  {
    id: 'short-explanation',
    code: 'ShortExplanation',
    category: 'explain',
    subjects: ['math', 'literature'],
    purpose: 'Коротко объясняет новое правило',
    is_assessment: false,
    content_schema: schema,
    rendering_notes: 'Simple text',
  },
  {
    id: 'mastery-check',
    code: 'MasteryCheck',
    category: 'assess',
    subjects: ['math'],
    purpose: 'Проверяет освоение темы',
    is_assessment: true,
    content_schema: schema,
    rendering_notes: 'Question set',
  },
  {
    id: 'argument-builder',
    code: 'ArgumentBuilder',
    category: 'communicate',
    subjects: ['literature'],
    purpose: 'Собирает аргумент по тексту',
    is_assessment: true,
    content_schema: schema,
    rendering_notes: 'Argument practice',
  },
];

describe('component catalog model', () => {
  it('formats category and subject labels with fallback for unknown values', () => {
    expect(categoryLabel('explain')).toBe('Объяснение');
    expect(categoryLabel('custom')).toBe('custom');
    expect(categoryStyle('assess')).toContain('rose');
    expect(categoryStyle('custom')).toContain('bg-muted');
    expect(subjectLabel('literature')).toBe('Литература');
    expect(subjectLabel('science')).toBe('Естественные науки');
    expect(subjectLabel('unknown')).toBe('unknown');
  });

  it('formats schema primitive, enum and array types', () => {
    expect(formatSchemaType({ type: 'number' })).toBe('number');
    expect(formatSchemaType({ enum: ['a', 'b'] })).toBe('"a" | "b"');
    expect(formatSchemaType({ items: { type: 'string' } })).toBe('string[]');
    expect(formatSchemaType({ items: { enum: ['x', 'y'] } })).toBe('"x" | "y"[]');
    expect(formatSchemaType({})).toBe('значение');
  });

  it('filters by query against id and purpose', () => {
    expect(filterComponents(components, 'правило', 'all').map((item) => item.id)).toEqual(['short-explanation']);
    expect(filterComponents(components, 'ARGUMENT', 'all').map((item) => item.id)).toEqual(['argument-builder']);
  });

  it('filters by assessment and subject facets', () => {
    expect(filterComponents(components, '', 'assessment').map((item) => item.id)).toEqual([
      'mastery-check',
      'argument-builder',
    ]);
    expect(filterComponents(components, '', 'math').map((item) => item.id)).toEqual([
      'short-explanation',
      'mastery-check',
    ]);
    expect(filterComponents(components, '', 'literature').map((item) => item.id)).toEqual([
      'short-explanation',
      'argument-builder',
    ]);
  });
});
