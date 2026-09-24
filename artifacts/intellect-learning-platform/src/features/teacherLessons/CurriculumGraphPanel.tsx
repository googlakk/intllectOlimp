import { useMemo } from 'react';
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Loader2, Network, RefreshCw } from 'lucide-react';

import { useBuildCurriculumGraph, useCurriculumGraph } from '@/lib/api';

export function CurriculumGraphPanel({ subjectId }: { subjectId: number }) {
  const graphQuery = useCurriculumGraph(subjectId);
  const buildGraph = useBuildCurriculumGraph(subjectId);
  const nodes = useMemo<Node[]>(() => (graphQuery.data?.topics ?? []).map((topic, index) => ({
    id: String(topic.id),
    position: { x: (index % 3) * 300, y: Math.floor(index / 3) * 170 },
    data: {
      label: (
        <div className="text-left">
          <div className="text-[11px] font-bold uppercase text-primary">{topic.section}</div>
          <div className="mt-1 font-bold text-foreground">{topic.name}</div>
          <div className="mt-2 text-xs text-muted-foreground">{topic.lesson_type === 'assessment' ? `Проверка по ${topic.covered_topic_ids?.length ?? 0} темам` : topic.lesson_type === 'review' ? `Повторение ${topic.covered_topic_ids?.length ?? 0} тем` : topic.lesson_type === 'reflection' ? 'Работа над ошибками' : `${topic.skills.filter(skill => skill.role === 'outcome').length} навыков`}</div>
        </div>
      ),
    },
    style: { width: 250, borderRadius: 8, border: '1px solid hsl(var(--border))', background: 'hsl(var(--card))', padding: 12 },
  })), [graphQuery.data]);
  const edges = useMemo<Edge[]>(() => (graphQuery.data?.edges ?? []).map((edge) => ({
    id: String(edge.id),
    source: String(edge.from_topic_id),
    target: String(edge.to_topic_id),
    type: 'smoothstep',
    animated: edge.relation === 'transfer' || edge.relation === 'cross_subject',
    label: edge.relation === 'progression' ? undefined : 'перенос навыка',
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { stroke: edge.relation === 'progression' ? 'hsl(var(--muted-foreground))' : 'hsl(var(--primary))' },
  })), [graphQuery.data]);

  return (
    <section className="overflow-hidden rounded-lg border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div>
          <div className="flex items-center gap-2 font-bold text-foreground"><Network className="h-5 w-5 text-primary" /> Карта навыков курса</div>
          <p className="mt-1 text-sm text-muted-foreground">Связи показывают последовательность и перенос освоенных навыков между темами.</p>
        </div>
        <button
          type="button"
          onClick={() => buildGraph.mutate()}
          disabled={buildGraph.isPending}
          className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-background px-4 text-sm font-bold text-foreground hover:bg-muted disabled:opacity-60"
        >
          {buildGraph.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Перестроить карту
        </button>
      </div>
      {graphQuery.isLoading ? (
        <div className="grid h-[520px] place-items-center"><Loader2 className="h-7 w-7 animate-spin text-primary" /></div>
      ) : nodes.length === 0 ? (
        <div className="grid h-56 place-items-center px-6 text-center text-sm text-muted-foreground">
          Постройте карту, чтобы увидеть навыки и зависимости тем.
        </div>
      ) : (
        <div className="h-[min(62vh,620px)] min-h-[420px] bg-background">
          <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable panOnScroll>
            <Background />
            <Controls />
          </ReactFlow>
        </div>
      )}
      {buildGraph.isError && <p className="border-t border-border px-5 py-3 text-sm font-semibold text-destructive">{(buildGraph.error as Error).message}</p>}
      {buildGraph.data && <p className="border-t border-border px-5 py-3 text-sm text-muted-foreground">Обработано тем: {buildGraph.data.topics}, навыков: {buildGraph.data.skills}, связей: {buildGraph.data.edges}.</p>}
      {(graphQuery.data?.cross_subject_opportunities.length ?? 0) > 0 && (
        <div className="border-t border-border px-5 py-5">
          <h3 className="text-sm font-extrabold uppercase text-foreground">Межпредметные варп-врата</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {graphQuery.data?.cross_subject_opportunities.slice(0, 8).map((opportunity) => (
              <div key={`${opportunity.from_topic_id}-${opportunity.to_topic_id}`} className="rounded-md border border-border bg-muted/20 p-4">
                <div className="text-xs font-bold uppercase text-primary">{opportunity.from_subject_name} → {opportunity.to_subject_name}</div>
                <div className="mt-1 text-sm font-bold text-foreground">{opportunity.from_topic_name} → {opportunity.to_topic_name}</div>
                <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{opportunity.rationale}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
