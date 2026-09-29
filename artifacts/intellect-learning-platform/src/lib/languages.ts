export type InstructionLanguage = 'ru' | 'ky' | 'en';

export const LANGUAGE_OPTIONS: { value: InstructionLanguage; label: string }[] = [
  { value: 'ru', label: 'Русский' },
  { value: 'ky', label: 'Кыргызский' },
  { value: 'en', label: 'Английский' },
];

export function isInstructionLanguage(value: unknown): value is InstructionLanguage {
  return LANGUAGE_OPTIONS.some((option) => option.value === value);
}

export function languageLabel(value: string | null | undefined): string {
  return LANGUAGE_OPTIONS.find((option) => option.value === value)?.label ?? 'Русский';
}
