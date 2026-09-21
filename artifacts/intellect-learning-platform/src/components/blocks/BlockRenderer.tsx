import React, { Suspense } from 'react';
import type { Block } from '@/lib/api/types';
import { isAssessmentBlock } from '@/lib/lessonBlocks';

type BlockComponentProps = Record<string, unknown> & {
  onAnswer?: (isCorrect: boolean) => void;
};
type BlockComponent = React.ComponentType<BlockComponentProps>;

function lazyBlock(importer: () => Promise<{ default: React.ComponentType<unknown> }>) {
  return React.lazy(importer) as React.LazyExoticComponent<BlockComponent>;
}

export const componentMap: Record<string, React.LazyExoticComponent<BlockComponent>> = {
  ShortExplanation: lazyBlock(() => import('./ShortExplanation')),
  KeyConcept: lazyBlock(() => import('./KeyConcept')),
  WorkedExample: lazyBlock(() => import('./WorkedExample')),
  GuidedPractice: lazyBlock(() => import('./GuidedPractice')),
  IndependentProblem: lazyBlock(() => import('./IndependentProblem')),
  RetrievalCheck: lazyBlock(() => import('./RetrievalCheck')),
  MindMap: lazyBlock(() => import('./MindMap')),
  Timeline: lazyBlock(() => import('./Timeline')),
  InteractiveGraph: lazyBlock(() => import('./InteractiveGraph')),
  TextEvidencePicker: lazyBlock(() => import('./TextEvidencePicker')),
  ArgumentBuilder: lazyBlock(() => import('./ArgumentBuilder')),
  Illustration: lazyBlock(() => import('./Illustration')),
  Presentation: lazyBlock(() => import('./Presentation')),
  MasteryCheck: lazyBlock(() => import('./MasteryCheck')),
  Reflection: lazyBlock(() => import('./Reflection')),
};

export interface BlockRendererProps {
  blocks: Block[];
  onAnswer?: (blockIndex: number, isCorrect: boolean) => void;
}

export default function BlockRenderer({ blocks, onAnswer }: BlockRendererProps) {
  if (!blocks || !Array.isArray(blocks)) return null;

  return (
    <div className="w-full max-w-4xl mx-auto space-y-2">
      {blocks.map((block, index) => {
        const Component = componentMap[block.component];
        const key = `block-${index}-${block.component}`;

        if (!Component) {
          return (
            <div key={key} className="border border-dashed border-destructive/50 bg-destructive/5 rounded-xl p-6 text-center my-6">
              <h4 className="text-destructive font-semibold mb-2">Неизвестный блок: {block.component}</h4>
              <p className="text-sm text-muted-foreground">Система не может отобразить этот тип контента.</p>
            </div>
          );
        }

        const isAssessment = isAssessmentBlock(block);
        const injectProps = isAssessment && onAnswer 
          ? { onAnswer: (isCorrect: boolean) => onAnswer(index, isCorrect) } 
          : {};

        return (
          <div key={key}>
            <Suspense fallback={<BlockLoadingFallback />}>
              <Component {...block.content} {...injectProps} />
            </Suspense>
          </div>
        );
      })}
    </div>
  );
}

function BlockLoadingFallback() {
  return (
    <div className="rounded-xl border border-border/60 bg-muted/20 p-6 text-sm font-medium text-muted-foreground">
      Загрузка блока...
    </div>
  );
}
