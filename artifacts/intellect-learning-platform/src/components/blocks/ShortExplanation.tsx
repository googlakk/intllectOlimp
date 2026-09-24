import { RichText } from './RichText';

export function parseMathText(text: string) {
  return <RichText text={text} inline />;
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
      
      {callout && (
        <div className="p-4 bg-primary/10 border-l-4 border-primary rounded-r-lg text-foreground">
          {parseMathText(callout)}
        </div>
      )}
    </div>
  );
}
