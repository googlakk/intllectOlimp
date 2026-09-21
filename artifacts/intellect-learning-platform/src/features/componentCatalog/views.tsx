import { useState } from 'react';
import { Blocks, CheckCircle2, Code2, Eye, Search } from 'lucide-react';
import type { ComponentRegistryEntry, ComponentSchema } from '@/lib/api/types';
import {
  CATALOG_FILTERS,
  categoryLabel,
  categoryStyle,
  formatSchemaType,
  subjectLabel,
  type ComponentCatalogFilter,
} from './model';

export function ComponentCatalogToolbar({
  filter,
  query,
  onFilterChange,
  onQueryChange,
}: {
  filter: ComponentCatalogFilter;
  query: string;
  onFilterChange: (filter: ComponentCatalogFilter) => void;
  onQueryChange: (query: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div className="relative w-full md:max-w-sm">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          data-testid="input-component-search"
          placeholder="Поиск компонента..."
          className="h-11 w-full rounded-xl border border-border bg-card pl-10 pr-4 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"
        />
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {CATALOG_FILTERS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            onClick={() => onFilterChange(value)}
            data-testid={`button-filter-${value}`}
            className={`whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold transition-colors ${
              filter === value
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'border border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function SchemaValue({ schema, depth = 0 }: { schema: ComponentSchema; depth?: number }) {
  if (schema.properties) {
    return (
      <div className={depth ? 'ml-4 border-l border-border pl-3' : 'space-y-2'}>
        {Object.entries(schema.properties).map(([name, property]) => (
          <div key={name} className="text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <code className="font-semibold text-foreground">{name}</code>
              {schema.required?.includes(name) && (
                <span className="text-[10px] font-semibold uppercase tracking-wide text-primary">обязательно</span>
              )}
              <span className="text-muted-foreground">{formatSchemaType(property)}</span>
            </div>
            {property.properties && <SchemaValue schema={property} depth={depth + 1} />}
            {property.items?.properties && <SchemaValue schema={property.items} depth={depth + 1} />}
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-muted-foreground">{formatSchemaType(schema)}</span>;
}

export function ComponentCard({
  component,
  onOpenDemo,
}: {
  component: ComponentRegistryEntry;
  onOpenDemo: (component: ComponentRegistryEntry) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <article className="group flex flex-col rounded-2xl border border-border bg-card shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md">
      <div className="flex items-start justify-between gap-4 border-b border-border/70 p-5">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Blocks className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <h2 className="truncate text-base font-bold text-foreground">{component.id}</h2>
              <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] font-semibold text-muted-foreground">
                {component.code}
              </span>
            </div>
            <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${categoryStyle(component.category)}`}>
              {categoryLabel(component.category)}
            </span>
          </div>
        </div>
        {component.is_assessment && (
          <span className="flex shrink-0 items-center gap-1 rounded-full bg-rose-500/10 px-2 py-1 text-[11px] font-semibold text-rose-700">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Оценивание
          </span>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-4 p-5">
        <div>
          <h3 className="mb-1 text-sm font-semibold text-foreground">{component.purpose}</h3>
          <p className="text-sm leading-relaxed text-muted-foreground">{component.rendering_notes}</p>
        </div>

        <div className="flex flex-wrap gap-1.5">
          {component.subjects.map((subject) => (
            <span key={subject} className="rounded-md border border-border bg-muted/50 px-2 py-1 text-[11px] font-medium text-muted-foreground">
              {subjectLabel(subject)}
            </span>
          ))}
        </div>

        <button
          type="button"
          onClick={() => onOpenDemo(component)}
          data-testid={`button-demo-${component.id}`}
          className="mt-auto flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-bold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
        >
          <Eye className="h-4 w-4" />
          Посмотреть демонстрацию
        </button>

        <div className="rounded-xl border border-border/80 bg-muted/20">
          <button
            type="button"
            onClick={() => setIsExpanded((expanded) => !expanded)}
            data-testid={`button-schema-${component.id}`}
            className="flex w-full items-center justify-between gap-3 px-3.5 py-3 text-left text-xs font-semibold text-foreground transition-colors hover:bg-muted/50"
            aria-expanded={isExpanded}
          >
            <span className="flex items-center gap-2">
              <Code2 className="h-4 w-4 text-primary" />
              Схема содержимого
            </span>
            <span className="text-muted-foreground">{isExpanded ? 'Скрыть' : 'Показать'}</span>
          </button>
          {isExpanded && (
            <div className="border-t border-border/80 px-3.5 py-3">
              <SchemaValue schema={component.content_schema} />
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
