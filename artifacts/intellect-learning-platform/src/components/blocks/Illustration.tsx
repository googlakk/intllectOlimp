import React from 'react';
import DOMPurify from 'dompurify';
import { parseMathText } from './ShortExplanation';

export interface IllustrationProps {
  title: string;
  description: string;
  svg_content: string;
  caption?: string;
}

export default function Illustration({ title, description, svg_content, caption }: IllustrationProps) {
  // Sanitize SVG safely
  const cleanSvg = DOMPurify.sanitize(svg_content, { 
    USE_PROFILES: { svg: true, svgFilters: true }
  });

  return (
    <div className="my-8 border rounded-xl overflow-hidden bg-card shadow-sm">
      <div className="p-6 border-b bg-muted/10">
        <h3 className="font-semibold text-xl text-foreground mb-2">{title}</h3>
        <div className="text-muted-foreground text-sm whitespace-pre-wrap leading-relaxed">
          {parseMathText(description)}
        </div>
      </div>
      
      <div className="p-6 bg-background flex justify-center items-center overflow-x-auto custom-scrollbar">
        <div 
          className="max-w-full"
          dangerouslySetInnerHTML={{ __html: cleanSvg }}
        />
      </div>
      
      {caption && (
        <div className="p-4 bg-muted/20 border-t text-sm text-center text-muted-foreground italic">
          {parseMathText(caption)}
        </div>
      )}
    </div>
  );
}
