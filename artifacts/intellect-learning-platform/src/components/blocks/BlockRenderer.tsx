import React, { Suspense } from 'react';
import type { Block } from '@/lib/api/types';
import { isAssessmentBlock } from '@/lib/lessonBlocks';

type BlockComponentProps = Record<string, unknown> & {
  onAnswer?: (isCorrect: boolean) => void;
};
type BlockComponent = React.ComponentType<BlockComponentProps>;
type BlockModule = { default: React.ComponentType<unknown> };
type BlockImporter = () => Promise<BlockModule>;

function lazyBlock(importer: BlockImporter) {
  return React.lazy(importer) as React.LazyExoticComponent<BlockComponent>;
}

export const blockLoaders: Record<string, BlockImporter> = {
  ShortExplanation: () => import('./ShortExplanation'),
  KeyConcept: () => import('./KeyConcept'),
  WorkedExample: () => import('./WorkedExample'),
  GuidedPractice: () => import('./GuidedPractice'),
  IndependentProblem: () => import('./IndependentProblem'),
  RetrievalCheck: () => import('./RetrievalCheck'),
  MindMap: () => import('./MindMap'),
  Timeline: () => import('./Timeline'),
  InteractiveGraph: () => import('./InteractiveGraph'),
  TextEvidencePicker: () => import('./TextEvidencePicker'),
  ArgumentBuilder: () => import('./ArgumentBuilder'),
  Illustration: () => import('./Illustration'),
  Presentation: () => import('./Presentation'),
  MasteryCheck: () => import('./MasteryCheck'),
  Reflection: () => import('./Reflection'),
  SortAndClassify: () => import('./SortAndClassify'),
  ProcessBuilder: () => import('./ProcessBuilder'),
  ArgumentMap: () => import('./ArgumentMap'),
  BranchingScenario: () => import('./BranchingScenario'),
  MisconceptionDebugger: () => import('./MisconceptionDebugger'),
  PredictionLab: () => import('./PredictionLab'),
  DataInvestigation: () => import('./DataInvestigation'),
  PhysicsSandbox: () => import('./PhysicsSandbox'),
  HotspotInvestigation: () => import('./HotspotInvestigation'),
  CodeBlocksLab: () => import('./CodeBlocksLab'),
  GeneratedMedia: () => import('./GeneratedMedia'),
};
const preloadCache = new Map<string, Promise<BlockModule>>();

export const componentMap: Record<string, React.LazyExoticComponent<BlockComponent>> = Object.fromEntries(
  Object.entries(blockLoaders).map(([name, importer]) => [name, lazyBlock(importer)]),
) as Record<string, React.LazyExoticComponent<BlockComponent>>;

export function preloadBlockComponent(componentName: string | undefined) {
  if (!componentName) return undefined;
  const importer = blockLoaders[componentName];
  if (!importer) return undefined;
  if (!preloadCache.has(componentName)) {
    preloadCache.set(componentName, importer());
  }
  return preloadCache.get(componentName);
}

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
