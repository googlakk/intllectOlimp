import React from 'react';
import ShortExplanation from './ShortExplanation';
import KeyConcept from './KeyConcept';
import WorkedExample from './WorkedExample';
import GuidedPractice from './GuidedPractice';
import IndependentProblem from './IndependentProblem';
import RetrievalCheck from './RetrievalCheck';
import MindMap from './MindMap';
import Timeline from './Timeline';
import InteractiveGraph from './InteractiveGraph';
import TextEvidencePicker from './TextEvidencePicker';
import ArgumentBuilder from './ArgumentBuilder';
import Illustration from './Illustration';
import Presentation from './Presentation';
import MasteryCheck from './MasteryCheck';
import Reflection from './Reflection';

export const componentMap: Record<string, React.ComponentType<any>> = {
  ShortExplanation,
  KeyConcept,
  WorkedExample,
  GuidedPractice,
  IndependentProblem,
  RetrievalCheck,
  MindMap,
  Timeline,
  InteractiveGraph,
  TextEvidencePicker,
  ArgumentBuilder,
  Illustration,
  Presentation,
  MasteryCheck,
  Reflection
};

export const assessmentComponents = [
  'GuidedPractice',
  'IndependentProblem',
  'RetrievalCheck',
  'TextEvidencePicker',
  'ArgumentBuilder',
  'MasteryCheck'
];

export interface Block {
  component: string;
  content: any;
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

        const isAssessment = assessmentComponents.includes(block.component);
        const injectProps = isAssessment && onAnswer 
          ? { onAnswer: (isCorrect: boolean) => onAnswer(index, isCorrect) } 
          : {};

        return (
          <div key={key}>
            <Component {...block.content} {...injectProps} />
          </div>
        );
      })}
    </div>
  );
}
