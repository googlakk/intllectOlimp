import React, { useState } from 'react';
import { parseMathText } from './ShortExplanation';
import { CheckCircle2, XCircle, HelpCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export interface GuidedPracticeProps {
  question: string;
  hints: string[];
  input_type: "text" | "numeric" | "expression" | "number" | "multiple_choice";
  correct_answer: string | string[];
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function GuidedPractice({ question, hints, input_type, correct_answer, explanation, onAnswer }: GuidedPracticeProps) {
  const [value, setValue] = useState('');
  const [status, setStatus] = useState<'idle' | 'correct' | 'incorrect'>('idle');
  const [hintIndex, setHintIndex] = useState(0);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;

    let isCorrect = false;
    const normalizedValue = value.trim().toLowerCase().replace(/\s+/g, ' ');
    
    if (Array.isArray(correct_answer)) {
      isCorrect = correct_answer.some(ans => ans.trim().toLowerCase().replace(/\s+/g, ' ') === normalizedValue);
    } else {
      isCorrect = normalizedValue === correct_answer.trim().toLowerCase().replace(/\s+/g, ' ');
    }
    
    setStatus(isCorrect ? 'correct' : 'incorrect');
    onAnswer?.(isCorrect);
  };

  const showNextHint = () => {
    if (hintIndex < hints.length) {
      setHintIndex(prev => prev + 1);
    }
  };

  const isLocked = status === 'correct';

  return (
    <div className="border rounded-xl p-6 my-6 bg-card shadow-sm transition-colors duration-300">
      <div className="mb-6">
        <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-primary"></span>
          Практика с подсказками
        </h3>
        <div className="text-foreground text-base p-4 bg-muted/20 rounded-lg whitespace-pre-wrap">{parseMathText(question)}</div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          <input
            type={input_type === 'numeric' || input_type === 'number' ? 'number' : 'text'}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              if (status !== 'idle') setStatus('idle');
            }}
            disabled={isLocked}
            placeholder={input_type === 'numeric' || input_type === 'number' ? "Введите число..." : "Введите ваш ответ..."}
            className="flex-1 px-4 py-2.5 border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 transition-all"
            aria-label="Ваш ответ"
            step="any"
          />
          <button
            type="submit"
            disabled={isLocked || !value.trim()}
            className="px-6 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            Проверить
          </button>
        </div>

        <AnimatePresence mode="wait">
          {status === 'correct' && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col gap-3"
            >
              <div className="flex items-center gap-2 text-green-700 dark:text-green-400 text-sm font-medium bg-green-500/10 border border-green-500/20 p-3.5 rounded-lg">
                <CheckCircle2 className="w-5 h-5 shrink-0" />
                <span>Верно! Отличная работа. (✓)</span>
              </div>
              <div className="p-4 bg-muted/30 border rounded-lg text-sm text-foreground">
                <span className="font-semibold block mb-1">Объяснение:</span>
                <div className="whitespace-pre-wrap">{parseMathText(explanation)}</div>
              </div>
            </motion.div>
          )}
          
          {status === 'incorrect' && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-2 text-destructive text-sm font-medium bg-destructive/10 border border-destructive/20 p-3.5 rounded-lg"
            >
              <XCircle className="w-5 h-5 shrink-0" />
              <span>Неверно. Попробуйте еще раз или используйте подсказку. (✗)</span>
            </motion.div>
          )}
        </AnimatePresence>

        {hints && hints.length > 0 && !isLocked && (
          <div className="mt-6 pt-4 border-t">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">
                Подсказки ({hintIndex} / {hints.length})
              </span>
              {hintIndex < hints.length && (
                <button
                  type="button"
                  onClick={showNextHint}
                  className="flex items-center gap-2 text-sm text-primary hover:text-primary/80 transition-colors font-medium"
                >
                  <HelpCircle className="w-4 h-4" />
                  Показать подсказку
                </button>
              )}
            </div>
            
            <div className="space-y-2">
              {hints.slice(0, hintIndex).map((hint, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  className="overflow-hidden"
                >
                  <div className="p-3 bg-muted/40 rounded-lg text-sm text-muted-foreground border border-border/50 whitespace-pre-wrap">
                    <span className="font-medium mr-2">Подсказка {i + 1}:</span>
                    {parseMathText(hint)}
                  </div>
                </motion.div>
              ))}
            </div>
          </div>
        )}
      </form>
    </div>
  );
}
