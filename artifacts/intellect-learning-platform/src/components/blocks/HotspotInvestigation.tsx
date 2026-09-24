import DOMPurify from 'dompurify';
import { useMemo, useState } from 'react';
import { BlockShell, PrimaryAction, ResultPanel } from './shared';
import { RichText } from './RichText';
import { sameSet, type BlockResult } from '@/features/interactiveEngines/scoring';

export type Hotspot = {
  id: string;
  label: string;
  x: number;
  y: number;
  feedback: string;
  is_correct?: boolean;
};

export interface HotspotInvestigationProps {
  title: string;
  instruction: string;
  svg_content: string;
  hotspots: Hotspot[];
  required_hotspots: string[];
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function HotspotInvestigation({ title, instruction, svg_content, hotspots, required_hotspots, explanation, onAnswer }: HotspotInvestigationProps) {
  const cleanSvg = useMemo(() => DOMPurify.sanitize(svg_content, { USE_PROFILES: { svg: true, svgFilters: true } }), [svg_content]);
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<BlockResult>('idle');
  const [feedback, setFeedback] = useState('');

  const toggle = (hotspot: Hotspot) => {
    setFeedback(hotspot.feedback);
    setSelected((current) => current.includes(hotspot.id)
      ? current.filter((id) => id !== hotspot.id)
      : [...current, hotspot.id]);
  };

  const check = () => {
    const ok = sameSet(selected, required_hotspots);
    setResult(ok ? 'correct' : selected.length ? 'partial' : 'incorrect');
    onAnswer?.(ok);
  };

  return (
    <BlockShell title={title} subtitle={instruction}>
      <div className="relative overflow-hidden rounded-xl border border-border bg-background p-3">
        <div className="[&_svg]:h-auto [&_svg]:w-full" dangerouslySetInnerHTML={{ __html: cleanSvg }} />
        {hotspots.map((hotspot) => (
          <button
            key={hotspot.id}
            onClick={() => toggle(hotspot)}
            className={`absolute flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border-2 text-xs font-bold shadow-md transition ${selected.includes(hotspot.id) ? 'border-primary bg-primary text-primary-foreground' : 'border-background bg-amber-400 text-amber-950 hover:scale-110'}`}
            style={{ left: `${hotspot.x}%`, top: `${hotspot.y}%` }}
            aria-label={hotspot.label}
            title={hotspot.label}
          >
            {hotspot.label.slice(0, 1)}
          </button>
        ))}
      </div>
      {feedback && <RichText text={feedback} className="mt-4 rounded-lg border border-border bg-muted/20 p-3 text-sm text-muted-foreground" />}
      <div className="mt-5 flex justify-end">
        <PrimaryAction onClick={check}>Проверить зоны</PrimaryAction>
      </div>
      <ResultPanel result={result} correctText={explanation} partialText={explanation} incorrectText={explanation} />
    </BlockShell>
  );
}
