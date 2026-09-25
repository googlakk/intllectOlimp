import { RichText } from './RichText';
import { BlockImage, blockImage } from './BlockMedia';

export function parseMathText(text: string) {
  return <RichText text={text} inline />;
}

export interface ShortExplanationProps {
  title: string;
  text: string;
  key_concepts: string[];
  callout?: string;
  media?: unknown;
}

export default function ShortExplanation({ title, text, key_concepts, callout, media }: ShortExplanationProps) {
  const hasImage = Boolean(blockImage(media));
  return (
    <div className="my-6">
      <h3 className="text-xl font-semibold mb-4 text-foreground">{title}</h3>
      {/* Картинка рядом с текстом, который она поясняет; на телефоне — сразу под заголовком. */}
      <div className={hasImage ? 'grid gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,40%)] md:items-start' : ''}>
        <div>
          <RichText text={text} className="mb-6 text-base leading-relaxed text-foreground" />

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
        </div>
        {hasImage && <BlockImage media={media} variant="side" className="order-first mb-1 md:order-none md:mb-6" />}
      </div>

      {callout && (
        <div className="p-4 bg-primary/10 border-l-4 border-primary rounded-r-lg text-foreground">
          {parseMathText(callout)}
        </div>
      )}
    </div>
  );
}
