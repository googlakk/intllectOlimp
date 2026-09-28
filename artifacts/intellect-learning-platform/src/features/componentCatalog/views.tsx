import { useEffect, useRef, useState } from 'react';
import { Eye, Search } from 'lucide-react';
import type { ComponentRegistryEntry } from '@/lib/api/types';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import type { ComponentDemo } from './demos';
import {
  CATALOG_FILTERS,
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

export function ComponentCard({
  component,
  demo,
  onOpenDemo,
}: {
  component: ComponentRegistryEntry;
  demo?: ComponentDemo;
  onOpenDemo: (component: ComponentRegistryEntry) => void;
}) {
  const previewRef = useRef<HTMLElement>(null);
  const [isPreviewVisible, setIsPreviewVisible] = useState(false);

  useEffect(() => {
    const element = previewRef.current;
    if (!element) return undefined;
    if (typeof IntersectionObserver === 'undefined') {
      setIsPreviewVisible(true);
      return undefined;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsPreviewVisible(entry.isIntersecting);
      },
      { rootMargin: '320px 0px' },
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  if (!demo) return null;

  const openDemo = () => onOpenDemo(component);

  return (
    <article
      ref={previewRef}
      className="group relative h-[360px] cursor-pointer overflow-hidden rounded-2xl border border-border bg-background shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-lg focus-within:ring-2 focus-within:ring-primary/40"
      data-testid={`component-preview-${component.id}`}
    >
      <div inert aria-hidden="true" className="pointer-events-none absolute left-0 top-0 w-[142.86%] origin-top-left scale-[0.7] p-5">
        {isPreviewVisible ? (
          <BlockRenderer blocks={[demo.block]} />
        ) : (
          <div className="h-[480px] animate-pulse rounded-2xl bg-muted/40" />
        )}
      </div>
      <button
        type="button"
        onClick={openDemo}
        data-testid={`button-demo-${component.id}`}
        aria-label={`Открыть демонстрацию: ${component.purpose}`}
        className="absolute inset-0 flex items-end justify-end bg-transparent p-3 outline-none"
      >
        <span className="flex translate-y-2 items-center gap-1.5 rounded-full bg-foreground/90 px-3 py-2 text-xs font-semibold text-background opacity-0 shadow-lg transition-all group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:translate-y-0 group-focus-within:opacity-100">
          <Eye className="h-3.5 w-3.5" />
          Открыть
        </span>
      </button>
    </article>
  );
}
