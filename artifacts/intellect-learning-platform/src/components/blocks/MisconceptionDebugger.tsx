import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core';
import { SortableContext, arrayMove, verticalListSortingStrategy, useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useState } from 'react';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { sameSet, type BlockResult } from '@/features/interactiveEngines/scoring';

export type DebugStep = {
  id: string;
  text: string;
  is_error?: boolean;
};

export interface MisconceptionDebuggerProps {
  title: string;
  prompt: string;
  steps: DebugStep[];
  repair_steps: string[];
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function MisconceptionDebugger({ title, prompt, steps, repair_steps, explanation, onAnswer }: MisconceptionDebuggerProps) {
  const [selectedError, setSelectedError] = useState<string>('');
  const [repairOrder, setRepairOrder] = useState(repair_steps.map((text, index) => ({ id: `repair-${index}`, text })).reverse());
  const [result, setResult] = useState<BlockResult>('idle');
  const sensors = useSensors(useSensor(PointerSensor), useSensor(KeyboardSensor));

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setRepairOrder((items) => {
      const oldIndex = items.findIndex((item) => item.id === active.id);
      const newIndex = items.findIndex((item) => item.id === over.id);
      return arrayMove(items, oldIndex, newIndex);
    });
  };

  const check = () => {
    const errorCorrect = steps.find((step) => step.id === selectedError)?.is_error === true;
    const orderCorrect = sameSet(repairOrder.map((item) => item.text), repair_steps)
      && repairOrder.every((item, index) => item.text === repair_steps[index]);
    const ok = errorCorrect && orderCorrect;
    setResult(ok ? 'correct' : errorCorrect ? 'partial' : 'incorrect');
    onAnswer?.(ok);
  };

  return (
    <BlockShell title={title} subtitle={prompt}>
      <div className="space-y-3">
        {steps.map((step, index) => (
          <button
            key={step.id}
            onClick={() => setSelectedError(step.id)}
            className={`w-full rounded-lg border p-4 text-left text-sm transition ${selectedError === step.id ? 'border-primary bg-primary/10' : 'border-border bg-card hover:border-primary/30'}`}
          >
            <span className="mr-2 font-mono text-muted-foreground">{index + 1}.</span>
            <RichText text={step.text} inline />
          </button>
        ))}
      </div>
      <div className="mt-6 rounded-lg border border-border bg-muted/20 p-4">
        <h4 className="mb-3 text-sm font-bold text-foreground">Соберите правильное исправление</h4>
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={repairOrder.map((item) => item.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {repairOrder.map((item) => <SortableRepair key={item.id} id={item.id} text={item.text} />)}
            </div>
          </SortableContext>
        </DndContext>
      </div>
      <div className="mt-5 flex justify-end">
        <PrimaryAction onClick={check} disabled={!selectedError}>Проверить разбор</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} partialText={explanation} incorrectText={explanation} />
    </BlockShell>
  );
}

function SortableRepair({ id, text }: { id: string; text: string }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
      className="cursor-grab rounded-lg border border-border bg-card p-3 text-sm font-medium shadow-sm active:cursor-grabbing"
    >
      <RichText text={text} inline />
    </div>
  );
}
