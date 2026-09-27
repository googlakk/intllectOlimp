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
  // Короткое нажатие — выбор элемента (на телефоне тащить через прокрутку неудобно), сдвиг — перетаскивание.
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }), useSensor(KeyboardSensor));
  const itemById = useMemo(() => new Map(items.map((item) => [item.id, item])), [items]);

  const onDragEnd = (event: DragEndEvent) => {
    const itemId = String(event.active.id);
    const groupId = event.over?.id ? String(event.over.id) : '';
    if (!itemById.has(itemId) || !groups.some((group) => group.id === groupId)) return;
    setPlacements((current) => ({ ...current, [itemId]: groupId }));
    setSelectedId(null);
  };

  const toggleSelect = (itemId: string) => setSelectedId((current) => (current === itemId ? null : itemId));
  const placeSelected = (groupId: string) => {
    if (!selectedId) return;
    setPlacements((current) => ({ ...current, [selectedId]: groupId }));
    setSelectedId(null);
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
            <h4 className="mb-1 text-sm font-bold text-foreground">Элементы</h4>
            <p className="mb-3 text-xs text-muted-foreground">Нажмите на элемент, затем на группу — или перетащите.</p>
            <div className="flex flex-wrap gap-2">
              {items.filter((item) => !placements[item.id]).map((item) => (
                <DraggableChip key={item.id} item={item} selected={selectedId === item.id} onSelect={toggleSelect} />
              ))}
              {items.every((item) => placements[item.id]) && (
                <p className="text-sm text-muted-foreground">Все элементы распределены.</p>
              )}
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {groups.map((group) => (
              <DropGroup key={group.id} group={group} armed={selectedId !== null} onPlace={placeSelected}>
                {items.filter((item) => placements[item.id] === group.id).map((item) => (
                  <DraggableChip key={item.id} item={item} selected={selectedId === item.id} onSelect={toggleSelect} />
                ))}
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

function DraggableChip({ item, selected, onSelect }: { item: SortItem; selected: boolean; onSelect: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id: item.id });
  return (
    <button
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      type="button"
      aria-pressed={selected}
      onClick={(event) => { event.stopPropagation(); onSelect(item.id); }}
      style={{ transform: transform ? `translate3d(${transform.x}px, ${transform.y}px, 0)` : undefined }}
      className={`touch-manipulation rounded-lg border px-3 py-2 text-sm font-semibold shadow-sm transition ${
        selected ? 'border-primary bg-primary text-primary-foreground ring-2 ring-primary/30' : 'border-border bg-card text-foreground hover:border-primary/40'
      }`}
    >
      <RichText text={item.label} inline />
    </button>
  );
}

function DropGroup({ group, armed, onPlace, children }: {
  group: SortGroup; armed: boolean; onPlace: (groupId: string) => void; children: React.ReactNode;
}) {
  const { isOver, setNodeRef } = useDroppable({ id: group.id });
  return (
    <div
      ref={setNodeRef}
      role={armed ? 'button' : undefined}
      tabIndex={armed ? 0 : undefined}
      aria-label={armed ? `Положить в группу «${group.label}»` : undefined}
      onClick={() => onPlace(group.id)}
      onKeyDown={(event) => { if (armed && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); onPlace(group.id); } }}
      className={`min-h-32 rounded-lg border p-4 transition-colors ${
        isOver ? 'border-primary bg-primary/10' : armed ? 'cursor-pointer border-dashed border-primary/60 bg-primary/5' : 'border-border bg-background'
      }`}
    >
      <div className="mb-3">
        <h4 className="text-sm font-bold text-foreground"><RichText text={group.label} inline /></h4>
        {group.hint && <RichText text={group.hint} className="mt-1 text-xs text-muted-foreground" />}
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}
