import { describe, expect, it } from 'vitest';

import type { AiModelGroup } from '@/lib/api';
import { resolveModelChoice } from './ModelPicker';

const group: AiModelGroup = {
  default: 'anthropic:claude-sonnet-4-6',
  options: [
    { id: 'anthropic:claude-sonnet-4-6', provider: 'anthropic', model: 'claude-sonnet-4-6', label: 'Sonnet 4.6', note: '', available: true, default: true },
    { id: 'anthropic:claude-opus-5', provider: 'anthropic', model: 'claude-opus-5', label: 'Opus 5', note: '', available: true, default: false },
    { id: 'openrouter:openai/gpt-6-sol', provider: 'openrouter', model: 'openai/gpt-6-sol', label: 'GPT-6 Sol', note: '', available: false, default: false },
  ],
};

describe('resolveModelChoice', () => {
  it('sends no model when the default is selected', () => {
    expect(resolveModelChoice(group, '')).toMatchObject({ value: group.default, requestModel: undefined });
    expect(resolveModelChoice(group, group.default).requestModel).toBeUndefined();
  });

  it('sends the remembered available model', () => {
    expect(resolveModelChoice(group, 'anthropic:claude-opus-5')).toMatchObject({
      value: 'anthropic:claude-opus-5',
      requestModel: 'anthropic:claude-opus-5',
    });
  });

  it('falls back to the default for unavailable or removed models', () => {
    expect(resolveModelChoice(group, 'openrouter:openai/gpt-6-sol').requestModel).toBeUndefined();
    expect(resolveModelChoice(group, 'vendor/removed').value).toBe(group.default);
  });

  it('works before the catalog has loaded', () => {
    expect(resolveModelChoice(undefined, 'anthropic:claude-opus-5')).toMatchObject({ value: '', requestModel: undefined });
  });
});
