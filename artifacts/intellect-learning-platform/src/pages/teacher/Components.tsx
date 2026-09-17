import { useMemo, useState } from 'react';
import { Blocks, CheckCircle2, Code2, Eye, Info, MousePointerClick, Search, Sparkles } from 'lucide-react';
import { useComponents, ComponentRegistryEntry, ComponentSchema } from '@/lib/api';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { componentDemos } from './componentDemos';

const categoryLabels: Record<string, string> = {
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

const categoryStyles: Record<string, string> = {
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

const subjectLabels: Record<string, string> = {
  math: 'Математика',
  literature: 'Литература',
};

function SchemaValue({ schema, depth = 0 }: { schema: ComponentSchema; depth?: number }) {
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

function formatSchemaType(schema: ComponentSchema) {
  if (schema.enum) return schema.enum.map((value) => `"${value}"`).join(' | ');
  if (schema.items) {
    const itemType = schema.items.enum
      ? schema.items.enum.map((value) => `"${value}"`).join(' | ')
      : schema.items.type ?? 'object';
    return `${itemType}[]`;
  }
  return schema.type ?? 'значение';
}

function ComponentCard({
  component,
  onOpenDemo,
}: {
  component: ComponentRegistryEntry;
  onOpenDemo: (component: ComponentRegistryEntry) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const categoryClass = categoryStyles[component.category] ?? 'bg-muted text-muted-foreground border-border';

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
            <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold ${categoryClass}`}>
              {categoryLabels[component.category] ?? component.category}
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
              {subjectLabels[subject] ?? subject}
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

export default function Components() {
  const { data: components, isLoading, isError } = useComponents();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<'all' | 'assessment' | 'math' | 'literature'>('all');
  const [selectedComponent, setSelectedComponent] = useState<ComponentRegistryEntry | null>(null);
  const selectedDemo = selectedComponent ? componentDemos[selectedComponent.id] : undefined;

  const filteredComponents = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return (components ?? []).filter((component) => {
      const matchesQuery = !normalizedQuery
        || component.id.toLowerCase().includes(normalizedQuery)
        || component.purpose.toLowerCase().includes(normalizedQuery);
      const matchesFilter = filter === 'all'
        || (filter === 'assessment' && component.is_assessment)
        || (filter === 'math' && component.subjects.includes('math'))
        || (filter === 'literature' && component.subjects.includes('literature'));
      return matchesQuery && matchesFilter;
    });
  }, [components, filter, query]);

  return (
    <div className="mx-auto max-w-7xl space-y-8">
      <header className="rounded-3xl border border-border bg-card p-6 shadow-sm md:p-8">
        <div className="flex flex-col justify-between gap-6 lg:flex-row lg:items-end">
          <div className="max-w-2xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Конструктор уроков
            </div>
            <h1 className="text-3xl font-bold tracking-tight text-foreground md:text-4xl">Библиотека компонентов</h1>
            <p className="mt-3 text-sm leading-relaxed text-muted-foreground md:text-base">
              Здесь собраны блоки, из которых ИИ формирует уроки. Откройте живую демонстрацию,
              чтобы увидеть компонент глазами ученика и попробовать его в действии.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3 rounded-2xl border border-border bg-muted/30 px-4 py-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
              <Blocks className="h-5 w-5" />
            </div>
            <div>
              <div className="text-2xl font-bold leading-none text-foreground">{components?.length ?? '—'}</div>
              <div className="mt-1 text-xs font-medium text-muted-foreground">доступных блоков</div>
            </div>
          </div>
        </div>
      </header>

      <section className="space-y-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="relative w-full md:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              data-testid="input-component-search"
              placeholder="Поиск компонента..."
              className="h-11 w-full rounded-xl border border-border bg-card pl-10 pr-4 text-sm outline-none transition-colors placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/20"
            />
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {[
              ['all', 'Все'],
              ['assessment', 'Проверка знаний'],
              ['math', 'Математика'],
              ['literature', 'Литература'],
            ].map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value as typeof filter)}
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

        {isLoading && (
          <div className="rounded-2xl border border-dashed border-border bg-card py-16 text-center text-sm font-medium text-muted-foreground">
            Загружаем библиотеку компонентов...
          </div>
        )}
        {isError && (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 py-16 text-center text-sm font-medium text-destructive">
            Не удалось загрузить библиотеку компонентов.
          </div>
        )}
        {!isLoading && !isError && filteredComponents.length === 0 && (
          <div className="rounded-2xl border border-dashed border-border bg-card py-16 text-center text-sm font-medium text-muted-foreground">
            По вашему запросу компоненты не найдены.
          </div>
        )}
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          {filteredComponents.map((component) => (
            <ComponentCard key={component.id} component={component} onOpenDemo={setSelectedComponent} />
          ))}
        </div>
      </section>

      <Dialog open={selectedComponent !== null} onOpenChange={(open) => !open && setSelectedComponent(null)}>
        <DialogContent
          className="max-h-[92vh] max-w-[min(1000px,calc(100vw-2rem))] overflow-y-auto p-0"
          data-testid="dialog-component-demo"
        >
          {selectedComponent && selectedDemo && (
            <>
              <DialogHeader className="border-b border-border bg-muted/20 px-6 py-5 text-left">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${categoryStyles[selectedComponent.category] ?? 'bg-muted text-muted-foreground border-border'}`}>
                    {categoryLabels[selectedComponent.category] ?? selectedComponent.category}
                  </span>
                  <span className="font-mono text-xs font-semibold text-muted-foreground">{selectedComponent.code}</span>
                </div>
                <DialogTitle className="text-2xl">{selectedComponent.purpose}</DialogTitle>
                <p className="text-sm text-muted-foreground">{selectedComponent.id}</p>
              </DialogHeader>

              <div className="space-y-6 px-4 py-5 sm:px-6">
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-bold text-foreground">
                      <Info className="h-4 w-4 text-blue-600" />
                      Когда использовать
                    </div>
                    <p className="text-sm leading-relaxed text-muted-foreground">{selectedDemo.usage}</p>
                  </div>
                  <div className="rounded-xl border border-violet-500/20 bg-violet-500/5 p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-bold text-foreground">
                      <MousePointerClick className="h-4 w-4 text-violet-600" />
                      Как попробовать
                    </div>
                    <p className="text-sm leading-relaxed text-muted-foreground">{selectedDemo.interaction}</p>
                  </div>
                </div>

                <div>
                  <div className="mb-3 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-bold uppercase tracking-wide text-foreground">Живая демонстрация</h3>
                  </div>
                  <div className="overflow-hidden rounded-2xl border border-border bg-background p-2 sm:p-4">
                    <BlockRenderer blocks={[selectedDemo.block]} />
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}