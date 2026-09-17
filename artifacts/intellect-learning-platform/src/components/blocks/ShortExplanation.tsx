import React from 'react';
import TeX from '@matejmazur/react-katex';

export const InlineMath = ({ math }: { math: string }) => <TeX math={math} />;
export const BlockMath = ({ math }: { math: string }) => <TeX math={math} block />;

export function parseMathText(text: string) {
  if (!text) return null;
  
  const blockRegex = /(\$\$[\s\S]*?\$\$)/g;
  const blocks = text.split(blockRegex);
  
  return blocks.map((block, i) => {
    if (block.startsWith('$$') && block.endsWith('$$')) {
      return <BlockMath key={`block-${i}`} math={block.slice(2, -2)} />;
    }
    
    const inlineRegex = /(\$[\s\S]*?\$)/g;
    const inlines = block.split(inlineRegex);
    
    return inlines.map((inline, j) => {
      if (inline.startsWith('$') && inline.endsWith('$')) {
        return <InlineMath key={`inline-${i}-${j}`} math={inline.slice(1, -1)} />;
      }
      return <React.Fragment key={`text-${i}-${j}`}>{inline}</React.Fragment>;
    });
  });
}

export interface ShortExplanationProps {
  title: string;
  text: string;
  key_concepts: string[];
  callout?: string;
}

export default function ShortExplanation({ title, text, key_concepts, callout }: ShortExplanationProps) {
  return (
    <div className="my-6">
      <h3 className="text-xl font-semibold mb-4 text-foreground">{title}</h3>
      <div className="text-foreground leading-relaxed mb-6 whitespace-pre-wrap text-base">
        {parseMathText(text)}
      </div>
      
      {key_concepts && key_concepts.length > 0 && (
        <div className="mb-6">
          <h4 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-3">Ключевые концепции</h4>
          <ul className="list-disc pl-5 space-y-2">
            {key_concepts.map((concept, index) => (
              <li key={index} className="text-foreground">
                {parseMathText(concept)}
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {callout && (
        <div className="p-4 bg-primary/10 border-l-4 border-primary rounded-r-lg text-foreground">
          {parseMathText(callout)}
        </div>
      )}
    </div>
  );
}
