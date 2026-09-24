import React, { Suspense } from 'react';
import { normalizeLessonMarkup } from '@/features/lessons/lessonContent';

const RichTextMarkdown = React.lazy(() => import('./RichTextMarkdown'));

const RICH_MARKUP_PATTERNS = [
  /\$[^$\n]+\$/,
  /\$\$[\s\S]*?\$\$/,
  /\\(?:sqrt|frac|times|div|cdot|pm|geq?|leq?|neq|left|right)\b/,
  /(^|\n)\s{0,3}(#{1,6}\s|\|.*\||[-*+]\s+|\d+[.)]\s+)/,
  /[*_~`[\]]/,
  /!\[[^\]]*\]\([^)]*\)/,
];

export function needsRichTextEngine(text: string): boolean {
  if (!text) return false;
  const normalized = normalizeLessonMarkup(text);
  return RICH_MARKUP_PATTERNS.some((pattern) => pattern.test(text) || pattern.test(normalized));
}

function PlainRichText({
  text,
  inline = false,
  className = '',
}: {
  text: string;
  inline?: boolean;
  className?: string;
}) {
  const normalized = normalizeLessonMarkup(text);
  if (inline) return <span className={className}>{normalized}</span>;
  return (
    <div className={className}>
      {normalized.split('\n').map((line, index) => (
        <p key={`${index}-${line}`} className="mb-3 last:mb-0">
          {line || '\u00a0'}
        </p>
      ))}
    </div>
  );
}

export function RichText({ text, inline = false, className = '' }: { text: string; inline?: boolean; className?: string }) {
  if (!text) return null;
  if (!needsRichTextEngine(text)) {
    return <PlainRichText text={text} inline={inline} className={className} />;
  }
  return (
    <Suspense fallback={<PlainRichText text={text} inline={inline} className={className} />}>
      <RichTextMarkdown text={text} inline={inline} className={className} />
    </Suspense>
  );
}
