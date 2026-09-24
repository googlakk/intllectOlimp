import type { ComponentRegistryEntry, ComponentSchema } from '@/lib/api/types';

export type ComponentCatalogFilter = 'all' | 'assessment' | 'math' | 'literature' | 'language' | 'science' | 'humanities' | 'computing' | 'arts_practical';

export const CATEGORY_LABELS: Record<string, string> = {
  explain: 'Объяснение',
  model: 'Разбор',
  practice: 'Практика',
  assess: 'Проверка',
  represent: 'Визуализация',
  interact: 'Интерактив',
  communicate: 'Аргументация',
  media: 'Медиа',
  reflect: 'Рефлексия',
};

export const CATEGORY_STYLES: Record<string, string> = {
  explain: 'bg-blue-500/10 text-blue-700 border-blue-500/20',
  model: 'bg-violet-500/10 text-violet-700 border-violet-500/20',
  practice: 'bg-amber-500/10 text-amber-700 border-amber-500/20',
  assess: 'bg-rose-500/10 text-rose-700 border-rose-500/20',
  represent: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20',
  interact: 'bg-cyan-500/10 text-cyan-700 border-cyan-500/20',
  communicate: 'bg-orange-500/10 text-orange-700 border-orange-500/20',
  media: 'bg-indigo-500/10 text-indigo-700 border-indigo-500/20',
  reflect: 'bg-slate-500/10 text-slate-700 border-slate-500/20',
};

export const SUBJECT_LABELS: Record<string, string> = {
  math: 'Математика',
  literature: 'Литература',
  language: 'Языки',
  science: 'Естественные науки',
  geography: 'География',
  humanities: 'Гуманитарные',
  computing: 'Информатика',
  arts_practical: 'Искусство/технология',
  physical_education: 'Физкультура',
};

export const CATALOG_FILTERS: Array<{ value: ComponentCatalogFilter; label: string }> = [
  { value: 'all', label: 'Все' },
  { value: 'assessment', label: 'Проверка знаний' },
  { value: 'math', label: 'Математика' },
  { value: 'literature', label: 'Литература' },
  { value: 'language', label: 'Языки' },
  { value: 'science', label: 'Естественные науки' },
  { value: 'humanities', label: 'Гуманитарные' },
  { value: 'computing', label: 'Информатика' },
  { value: 'arts_practical', label: 'Практика' },
];

export function categoryLabel(category: string): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function categoryStyle(category: string): string {
  return CATEGORY_STYLES[category] ?? 'bg-muted text-muted-foreground border-border';
}

export function subjectLabel(subject: string): string {
  return SUBJECT_LABELS[subject] ?? subject;
}

export function formatSchemaType(schema: ComponentSchema): string {
  if (schema.enum) return schema.enum.map((value) => `"${value}"`).join(' | ');
  if (schema.items) {
    const itemType = schema.items.enum
      ? schema.items.enum.map((value) => `"${value}"`).join(' | ')
      : schema.items.type ?? 'object';
    return `${itemType}[]`;
  }
  return schema.type ?? 'значение';
}

export function filterComponents(
  components: ComponentRegistryEntry[] | undefined,
  query: string,
  filter: ComponentCatalogFilter,
): ComponentRegistryEntry[] {
  const normalizedQuery = query.trim().toLowerCase();
  return (components ?? []).filter((component) => {
    const matchesQuery = !normalizedQuery
      || component.id.toLowerCase().includes(normalizedQuery)
      || component.purpose.toLowerCase().includes(normalizedQuery);
    const matchesFilter = filter === 'all'
      || (filter === 'assessment' && component.is_assessment)
      || (filter !== 'assessment' && component.subjects.includes(filter));
    return matchesQuery && matchesFilter;
  });
}
