import { DndContext, KeyboardSensor, PointerSensor, useDraggable, useDroppable, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core';
import { useMemo, useState } from 'react';
import type React from 'react';
import { PrimaryAction, ResultPanel, BlockShell } from './shared';
import { RichText } from './RichText';
import { resultFromScore, scoreRatio, type BlockResult } from '@/features/interactiveEngines/scoring';

export type SortItem = {
  id: string;
  label: string;
  correct_group: string;
};

export type SortGroup = {
  id: string;
  label: string;
  hint?: string;
};

export interface SortAndClassifyProps {
  title: string;
  instruction: string;
  items: SortItem[];
  groups: SortGroup[];
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function SortAndClassify({ title, instruction, items, groups, explanation, onAnswer }: SortAndClassifyProps) {
  const [placements, setPlacements] = useState<Record<string, string>>({});
  const [result, setResult] = useState<BlockResult>('idle');
  const sensors = useSensors(useSensor(PointerSensor), useSensor(KeyboardSensor));
  const itemById = useMemo(() => new Map(items.map((item) => [item.id, item])), [items]);

  const onDragEnd = (event: DragEndEvent) => {
    const itemId = String(event.active.id);
    const groupId = event.over?.id ? String(event.over.id) : '';
    if (!itemById.has(itemId) || !groups.some((group) => group.id === groupId)) return;
    setPlacements((current) => ({ ...current, [itemId]: groupId }));
  };

  const check = () => {
    const correct = items.filter((item) => placements[item.id] === item.correct_group).length;
    const score = scoreRatio(correct, items.length);
    const next = resultFromScore(score);
    setResult(next);
    onAnswer?.(score >= 80);
  };

  return (
    <BlockShell title={title} subtitle={instruction}>
      <DndContext sensors={sensors} onDragEnd={onDragEnd}>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.4fr)]">
          <div className="rounded-lg border border-border bg-muted/20 p-4">
            <h4 className="mb-3 text-sm font-bold text-foreground">Элементы</h4>
            <div className="flex flex-wrap gap-2">
              {items.filter((item) => !placements[item.id]).map((item) => <DraggableChip key={item.id} item={item} />)}
              {items.every((item) => placements[item.id]) && (
                <p className="text-sm text-muted-foreground">Все элементы распределены.</p>
              )}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {groups.map((group) => (
              <DropGroup key={group.id} group={group}>
                {items.filter((item) => placements[item.id] === group.id).map((item) => <DraggableChip key={item.id} item={item} />)}
              </DropGroup>
            ))}
          </div>
        </div>
      </DndContext>
      <div className="mt-5 flex justify-end">
        <PrimaryAction onClick={check} disabled={Object.keys(placements).length < items.length}>Проверить классификацию</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} partialText={explanation} incorrectText={explanation} />
    </BlockShell>
  );
}

function DraggableChip({ item }: { item: SortItem }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: item.id });
  return (
    <button
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={{ transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined }}
      className="touch-none rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-foreground shadow-sm transition hover:border-primary/40"
    >
      <RichText text={item.label} inline />
    </button>
  );
}

function DropGroup({ group, children }: { group: SortGroup; children: React.ReactNode }) {
  const { isOver, setNodeRef } = useDroppable({ id: group.id });
  return (
    <div
      ref={setNodeRef}
      className={`min-h-32 rounded-lg border p-4 transition-colors ${isOver ? 'border-primary bg-primary/10' : 'border-border bg-background'}`}
    >
      <div className="mb-3">
        <h4 className="text-sm font-bold text-foreground"><RichText text={group.label} inline /></h4>
        {group.hint && <RichText text={group.hint} className="mt-1 text-xs text-muted-foreground" />}
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}
