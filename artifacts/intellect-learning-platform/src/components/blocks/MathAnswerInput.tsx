import { useMemo, useRef } from 'react';
import katex from 'katex';
import { mathToLatex, parseMath } from '@/features/interactiveEngines/mathExpression';

type Props = {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  /** Кнопки дроби, корня и степени и запись «как в тетради» — для ответов-выражений и чисел. */
  mathTools?: boolean;
  className?: string;
};

// Вставка: текст до курсора и после; выделенное попадает внутрь (в числитель, под корень).
const TOOLS: { label: string; title: string; before: string; after: string }[] = [
  { label: 'a/b', title: 'Дробь', before: '(', after: ')/()' },
  { label: '√', title: 'Квадратный корень', before: '√(', after: ')' },
  { label: 'x²', title: 'Квадрат', before: '', after: '^2' },
  { label: 'xⁿ', title: 'Степень', before: '', after: '^' },
  { label: '( )', title: 'Скобки', before: '(', after: ')' },
];

/** Поле ответа. Для математики — кнопки и предпросмотр: 3/4 видно дробью, sqrt(12) — корнем. */
export default function MathAnswerInput({ value, onChange, disabled, placeholder, mathTools, className }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const preview = useMemo(() => {
    // Простое число показывать незачем: предпросмотр нужен, когда в записи есть дробь, корень, степень.
    if (!mathTools || !/[/√^²³*:()a-z]|sqrt/i.test(value)) return null;
    const node = parseMath(value);
    if (!node) return null;
    try {
      return katex.renderToString(mathToLatex(node), { throwOnError: false });
    } catch {
      return null;
    }
  }, [mathTools, value]);

  const insert = (before: string, after: string) => {
    const input = inputRef.current;
    const start = input?.selectionStart ?? value.length;
    const end = input?.selectionEnd ?? value.length;
    const selected = value.slice(start, end);
    // Дробь без выделения: курсор в числитель; с выделением — оно числитель, курсор в знаменатель.
    const next = value.slice(0, start) + before + selected + after + value.slice(end);
    onChange(next);
    // Степень: курсор после знака; дробь с выделением — в знаменатель; иначе — внутрь скобок.
    const caret = !before ? start + selected.length + after.length
      : selected && after.endsWith('()') ? start + before.length + selected.length + after.length - 1
        : start + before.length + selected.length;
    requestAnimationFrame(() => {
      input?.focus();
      input?.setSelectionRange(caret, caret);
    });
  };

  return (
    <div className="flex-1 min-w-0 space-y-2">
      <input
        ref={inputRef}
        type="text"
        inputMode={mathTools ? 'text' : undefined}
        autoCapitalize="off"
        autoCorrect="off"
        spellCheck={false}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        aria-label="Ваш ответ"
        className={className ?? 'w-full px-4 py-2.5 border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 transition-all'}
      />
      {mathTools && !disabled && (
        <div className="flex flex-wrap items-center gap-1.5" role="toolbar" aria-label="Математические знаки">
          {TOOLS.map((tool) => (
            <button
              key={tool.title}
              type="button"
              title={tool.title}
              aria-label={tool.title}
              // Не забираем фокус у поля: курсор остаётся на месте вставки.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => insert(tool.before, tool.after)}
              className="min-w-10 h-9 px-2.5 rounded-md border bg-muted/40 text-sm font-medium hover:bg-primary/10 hover:border-primary/40 transition-colors"
            >
              {tool.label}
            </button>
          ))}
        </div>
      )}
      {preview && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground" aria-hidden="true">
          <span>Запись:</span>
          <span className="text-lg text-foreground" dangerouslySetInnerHTML={{ __html: preview }} />
        </div>
      )}
    </div>
  );
}
