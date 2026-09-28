import { useMemo, useState } from 'react';
import { Link } from 'wouter';
import { Blocks, Info, MousePointerClick, Sparkles } from 'lucide-react';
import { useComponents, type ComponentRegistryEntry } from '@/lib/api';
import BlockRenderer from '@/components/blocks/BlockRenderer';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { componentDemos } from '@/features/componentCatalog/demos';
import { ComponentCard, ComponentCatalogToolbar } from '@/features/componentCatalog/views';
import { CatalogLessonPicker } from '@/features/componentCatalog/CatalogLessonPicker';
import { categoryLabel, categoryStyle, filterComponents, type ComponentCatalogFilter } from '@/features/componentCatalog/model';

export default function Components() {
  const { data: components, isLoading, isError } = useComponents();
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<ComponentCatalogFilter>('all');
  const [selectedComponent, setSelectedComponent] = useState<ComponentRegistryEntry | null>(null);
  const selectedDemo = selectedComponent ? componentDemos[selectedComponent.id] : undefined;

  const filteredComponents = useMemo(
    () => filterComponents(components, query, filter),
    [components, filter, query],
  );

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
            <Link href="/visual/mini-games" className="mt-4 inline-flex items-center gap-2 rounded-full bg-[#263530] px-4 py-2 text-sm font-semibold text-white"><Sparkles size={16} /> 7 новых мини-игр · попробовать</Link>
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
        <ComponentCatalogToolbar
          filter={filter}
          query={query}
          onFilterChange={setFilter}
          onQueryChange={setQuery}
        />

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
            <ComponentCard
              key={component.id}
              component={component}
              demo={componentDemos[component.id]}
              onOpenDemo={setSelectedComponent}
            />
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
                  <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${categoryStyle(selectedComponent.category)}`}>
                    {categoryLabel(selectedComponent.category)}
                  </span>
                  <span className="font-mono text-xs font-semibold text-muted-foreground">{selectedComponent.code}</span>
                </div>
                <DialogTitle className="text-2xl">{selectedComponent.purpose}</DialogTitle>
                <p className="text-sm text-muted-foreground">{selectedComponent.id}</p>
              </DialogHeader>

              <div className="space-y-6 px-4 py-5 sm:px-6">
                <CatalogLessonPicker key={selectedComponent.id} componentId={selectedComponent.id} />
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
