import { useState } from 'react';
import type { AiModelGroup, AiModelOption } from '@/lib/api';

function readStored(key: string): string {
  try {
    return globalThis.localStorage?.getItem(key) ?? '';
  } catch {
    return '';
  }
}

function writeStored(key: string, value: string) {
  try {
    globalThis.localStorage?.setItem(key, value);
  } catch {
    /* Выбор просто не запомнится — генерация от этого не зависит. */
  }
}

export type ModelChoice = {
  value: string;
  selected: AiModelOption | undefined;
  /** id для запроса; undefined — сервер возьмёт модель по умолчанию. */
  requestModel: string | undefined;
  setValue: (id: string) => void;
};

/** Недоступный или неизвестный сохранённый выбор откатывается к модели по умолчанию. */
export function resolveModelChoice(group: AiModelGroup | undefined, stored: string) {
  const options = group?.options ?? [];
  const remembered = options.find(option => option.id === stored && option.available);
  const value = remembered?.id ?? group?.default ?? '';
  return {
    value,
    selected: options.find(option => option.id === value),
    requestModel: value && value !== group?.default ? value : undefined,
  };
}

/** Запоминает выбор учителя в этом браузере. */
export function useModelChoice(group: AiModelGroup | undefined, storageKey: string): ModelChoice {
  const [stored, setStored] = useState(() => readStored(storageKey));
  return {
    ...resolveModelChoice(group, stored),
    setValue: (id: string) => {
      setStored(id);
      writeStored(storageKey, id);
    },
  };
}

export default function ModelPicker({ label, group, choice, disabled, loadError }: {
  label: string;
  group: AiModelGroup | undefined;
  choice: ModelChoice;
  disabled?: boolean;
  loadError?: boolean;
}) {
  if (loadError) return <p className="text-xs text-muted-foreground">Список моделей недоступен — будет использована модель по умолчанию.</p>;
  if (!group) return null;
  return (
    <label className="block text-xs font-semibold text-muted-foreground">
      {label}
      <select
        value={choice.value}
        disabled={disabled}
        onChange={event => choice.setValue(event.target.value)}
        className="mt-1 h-10 w-full rounded-lg border border-border bg-card px-3 text-sm font-semibold text-foreground disabled:opacity-60"
      >
        {group.options.map(option => (
          <option key={option.id} value={option.id} disabled={!option.available}>
            {option.label}{option.default ? ' · по умолчанию' : ''}{option.available ? '' : ' — нет ключа на сервере'}
          </option>
        ))}
      </select>
      {choice.selected?.note && <span className="mt-1 block font-normal">{choice.selected.note}</span>}
    </label>
  );
}
