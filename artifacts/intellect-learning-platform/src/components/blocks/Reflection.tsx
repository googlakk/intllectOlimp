import React, { useState } from 'react';
import { parseMathText } from './ShortExplanation';

export interface ReflectionProps {
  prompt: string;
  scale_question: string;
  scale_labels: string[];
}

export default function Reflection({ prompt, scale_question, scale_labels }: ReflectionProps) {
  const [selectedValue, setSelectedValue] = useState<number | null>(null);
  const [textAnswer, setTextAnswer] = useState('');
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedValue !== null) {
      setIsSubmitted(true);
    }
  };

  return (
    <div className="border border-primary/20 rounded-2xl p-6 md:p-8 my-8 bg-gradient-to-br from-primary/5 to-transparent shadow-sm">
      <div className="mb-8">
        <span className="inline-block px-3 py-1 bg-primary/10 text-primary text-xs font-bold rounded-full mb-4 uppercase tracking-widest">
          Рефлексия
        </span>
        <h3 className="text-xl font-medium text-foreground mb-4 whitespace-pre-wrap">
          {parseMathText(prompt)}
        </h3>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Scale Question */}
        <div>
          <label className="block font-medium text-foreground mb-4">
            {parseMathText(scale_question)}
          </label>
          <div className="flex flex-col sm:flex-row gap-2 sm:gap-0 w-full rounded-xl overflow-hidden shadow-sm border">
            {scale_labels.map((label, index) => (
              <button
                key={index}
                type="button"
                onClick={() => !isSubmitted && setSelectedValue(index)}
                disabled={isSubmitted}
                className={`flex-1 p-3 sm:py-4 text-sm font-medium transition-colors sm:border-r last:border-r-0 ${
                  selectedValue === index 
                    ? 'bg-primary text-primary-foreground' 
                    : 'bg-card text-muted-foreground hover:bg-muted disabled:opacity-50'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Text Area */}
        <div>
          <label className="block text-sm font-medium text-foreground mb-2">
            Дополнительные мысли (необязательно):
          </label>
          <textarea
            value={textAnswer}
            onChange={(e) => setTextAnswer(e.target.value)}
            disabled={isSubmitted}
            placeholder="Ваши размышления..."
            className="w-full p-4 border rounded-xl bg-card resize-none min-h-[120px] focus:outline-none focus:ring-2 focus:ring-primary shadow-sm disabled:opacity-50 text-sm"
          />
        </div>

        {!isSubmitted ? (
          <button
            type="submit"
            disabled={selectedValue === null}
            className="w-full sm:w-auto px-8 py-3 bg-foreground text-background rounded-xl font-medium hover:bg-foreground/90 disabled:opacity-50 transition-colors shadow-sm"
          >
            Сохранить ответ
          </button>
        ) : (
          <div className="p-4 bg-green-500/10 border border-green-500/20 text-green-700 dark:text-green-400 rounded-xl text-center font-medium">
            Спасибо за ваши размышления!
          </div>
        )}
      </form>
    </div>
  );
}
