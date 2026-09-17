import React, { useState } from 'react';
import { parseMathText } from './ShortExplanation';
import { CheckCircle2, XCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export interface RetrievalCheckProps {
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function RetrievalCheck({ question, options, correct_answer, explanation, onAnswer }: RetrievalCheckProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [status, setStatus] = useState<'idle' | 'correct' | 'incorrect'>('idle');

  const handleSelect = (opt: string) => {
    if (status !== 'idle') return;
    
    setSelected(opt);
    const normalizedSelected = opt.trim().toLowerCase().replace(/\s+/g, ' ');
    const normalizedCorrect = correct_answer.trim().toLowerCase().replace(/\s+/g, ' ');
    
    const isCorrect = normalizedSelected === normalizedCorrect;
    setStatus(isCorrect ? 'correct' : 'incorrect');
    onAnswer?.(isCorrect);
  };

  const isLocked = status !== 'idle';

  return (
    <div className="border rounded-2xl p-8 my-8 bg-gradient-to-b from-card to-muted/20 shadow-sm text-center relative overflow-hidden">
      <div className="absolute -top-10 -right-10 w-32 h-32 bg-primary/5 rounded-full blur-2xl pointer-events-none" />
      <div className="absolute -bottom-10 -left-10 w-32 h-32 bg-secondary/5 rounded-full blur-2xl pointer-events-none" />
      
      <div className="relative z-10">
        <span className="inline-block px-3 py-1 bg-primary/10 text-primary text-xs font-bold rounded-full mb-6 uppercase tracking-widest">
          Проверка знаний
        </span>
        <h3 className="text-xl font-medium mb-8 text-foreground leading-relaxed max-w-2xl mx-auto whitespace-pre-wrap">
          {parseMathText(question)}
        </h3>

        <div className="max-w-md mx-auto space-y-3">
          {options.map((opt, i) => {
            const isSelected = selected === opt;
            const isCorrectOption = opt.trim().toLowerCase().replace(/\s+/g, ' ') === correct_answer.trim().toLowerCase().replace(/\s+/g, ' ');
            
            let btnClass = "w-full text-left px-5 py-4 border rounded-xl text-base transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-primary";
            
            if (isLocked) {
              if (isCorrectOption) {
                btnClass += " bg-green-50 border-green-500 text-green-900 dark:bg-green-900/30 dark:border-green-400 dark:text-green-100";
              } else if (isSelected && !isCorrectOption) {
                btnClass += " bg-red-50 border-red-500 text-red-900 dark:bg-red-900/30 dark:border-red-400 dark:text-red-100";
              } else {
                btnClass += " bg-background opacity-60";
              }
            } else {
              btnClass += " bg-background hover:border-primary hover:bg-primary/5";
            }

            return (
              <button
                key={i}
                onClick={() => handleSelect(opt)}
                disabled={isLocked}
                className={btnClass}
              >
                {parseMathText(opt)}
              </button>
            );
          })}

          <AnimatePresence mode="wait">
            {status === 'correct' && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="mt-6"
              >
                <div className="flex justify-center items-center gap-2 text-green-600 dark:text-green-400 font-medium mb-4">
                  <CheckCircle2 className="w-5 h-5" />
                  <span>Абсолютно верно! (✓)</span>
                </div>
                <div className="text-left p-4 bg-muted/50 rounded-lg text-sm text-foreground">
                  <span className="font-semibold block mb-1">Объяснение:</span>
                  <div className="whitespace-pre-wrap">{parseMathText(explanation)}</div>
                </div>
              </motion.div>
            )}
            
            {status === 'incorrect' && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="mt-6"
              >
                <div className="flex justify-center items-center gap-2 text-destructive font-medium mb-4">
                  <XCircle className="w-5 h-5" />
                  <span>Неверно (✗)</span>
                </div>
                <div className="text-left p-4 bg-muted/50 rounded-lg text-sm text-foreground">
                  <span className="font-semibold block mb-1">Объяснение:</span>
                  <div className="whitespace-pre-wrap">{parseMathText(explanation)}</div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
