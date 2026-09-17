import React from 'react';
import { Lightbulb } from 'lucide-react';
import { parseMathText } from './ShortExplanation';

export interface KeyConceptProps {
  term: string;
  definition: string;
  example: string;
  non_example: string;
  visual_hint?: string;
}

export default function KeyConcept({ term, definition, example, non_example, visual_hint }: KeyConceptProps) {
  return (
    <div className="rounded-xl border border-primary/20 bg-primary/5 p-5 my-6">
      <div className="flex items-start gap-4 mb-4">
        <div className="mt-0.5 text-primary flex-shrink-0">
          <Lightbulb className="w-6 h-6" />
        </div>
        <div>
          <h4 className="font-semibold text-foreground text-lg mb-1">{parseMathText(term)}</h4>
          <div className="text-muted-foreground text-sm leading-relaxed whitespace-pre-wrap">
            {parseMathText(definition)}
          </div>
        </div>
      </div>
      
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-4">
        <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-lg">
          <span className="text-xs font-semibold text-green-700 dark:text-green-400 uppercase tracking-wider mb-2 block">Пример</span>
          <div className="text-sm text-foreground whitespace-pre-wrap">{parseMathText(example)}</div>
        </div>
        <div className="bg-destructive/10 border border-destructive/20 p-4 rounded-lg">
          <span className="text-xs font-semibold text-destructive uppercase tracking-wider mb-2 block">Антипример</span>
          <div className="text-sm text-foreground whitespace-pre-wrap">{parseMathText(non_example)}</div>
        </div>
      </div>

      {visual_hint && (
        <div className="mt-4 p-3 bg-muted/50 rounded-lg text-sm text-muted-foreground italic">
          <span className="font-medium mr-2 not-italic">💡 Визуальная подсказка:</span>
          {parseMathText(visual_hint)}
        </div>
      )}
    </div>
  );
}
