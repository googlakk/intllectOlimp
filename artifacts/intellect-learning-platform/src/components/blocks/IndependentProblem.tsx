import React, { useState } from 'react';
import { parseMathText } from './ShortExplanation';
import { CheckCircle2, XCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export interface IndependentProblemProps {
  question: string;
  type: "text" | "number" | "multiple_choice";
  options?: string[];
  correct_answer: string | string[];
  explanation: string;
  difficulty: "easy" | "medium" | "hard";
  onAnswer?: (isCorrect: boolean) => void;
}

export default function IndependentProblem({ question, type, options, correct_answer, explanation, difficulty, onAnswer }: IndependentProblemProps) {
  const [value, setValue] = useState('');
  const [status, setStatus] = useState<'idle' | 'correct' | 'incorrect'>('idle');
  const [attempts, setAttempts] = useState(0);

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!value.trim()) return;

    let isCorrect = false;
    const normalizedValue = value.trim().toLowerCase().replace(/\s+/g, ' ');
    
    if (Array.isArray(correct_answer)) {
      isCorrect = correct_answer.some(ans => ans.trim().toLowerCase().replace(/\s+/g, ' ') === normalizedValue);
    } else {
      isCorrect = normalizedValue === correct_answer.trim().toLowerCase().replace(/\s+/g, ' ');
    }
    
    setStatus(isCorrect ? 'correct' : 'incorrect');
    if (!isCorrect) {
      setAttempts(a => a + 1);
    }
    onAnswer?.(isCorrect);
  };

  const isLocked = status === 'correct' || attempts >= 3;

  const difficultyColors = {
    easy: "bg-green-500/20 text-green-700 dark:text-green-400",
    medium: "bg-yellow-500/20 text-yellow-700 dark:text-yellow-400",
    hard: "bg-red-500/20 text-red-700 dark:text-red-400"
  };
  
  const difficultyLabels = {
    easy: "Легкая",
    medium: "Средняя",
    hard: "Сложная"
  };

  return (
    <div className="border rounded-xl p-6 my-6 bg-card shadow-sm">
      <div className="flex justify-between items-start mb-6">
        <h3 className="font-semibold text-lg flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-secondary"></span>
          Самостоятельное решение
        </h3>
        <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${difficultyColors[difficulty]}`}>
          {difficultyLabels[difficulty]}
        </span>
      </div>
      
      <div className="text-foreground p-4 bg-muted/20 rounded-lg whitespace-pre-wrap mb-6">
        {parseMathText(question)}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {type === 'multiple_choice' && options ? (
          <div className="space-y-2 mb-4">
            {options.map((opt, i) => (
              <label 
                key={i}
                className={`flex items-start p-3 border rounded-lg cursor-pointer transition-colors ${
                  value === opt ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                } ${isLocked ? 'opacity-70 pointer-events-none' : ''}`}
              >
                <input
                  type="radio"
                  name={`question-${question.substring(0,10)}`}
                  value={opt}
                  checked={value === opt}
                  onChange={(e) => {
                    setValue(e.target.value);
                    if (status === 'incorrect' && attempts < 3) setStatus('idle');
                  }}
                  disabled={isLocked}
                  className="mt-1 mr-3 text-primary focus:ring-primary h-4 w-4"
                />
                <span className="text-sm">{parseMathText(opt)}</span>
              </label>
            ))}
          </div>
        ) : (
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <input
              type={type === 'number' ? 'number' : 'text'}
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                if (status === 'incorrect' && attempts < 3) {
                   setStatus('idle');
                }
              }}
              disabled={isLocked}
              placeholder="Ваш ответ..."
              className="flex-1 px-4 py-2.5 border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50 transition-all"
              step="any"
            />
          </div>
        )}

        <div className="flex items-center justify-between">
          <button
            type={type === 'multiple_choice' ? 'button' : 'submit'}
            onClick={type === 'multiple_choice' ? () => handleSubmit() : undefined}
            disabled={isLocked || !value.trim()}
            className="px-6 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            Ответить
          </button>
          {!isLocked && attempts > 0 && attempts < 3 && (
            <div className="text-xs text-muted-foreground">
              Осталось попыток: {3 - attempts}
            </div>
          )}
        </div>

        <AnimatePresence mode="wait">
          {status === 'correct' && (
            <motion.div 
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex flex-col gap-3 mt-4"
            >
              <div className="flex items-center gap-2 text-green-700 dark:text-green-400 text-sm font-medium bg-green-500/10 border border-green-500/20 p-3.5 rounded-lg">
                <CheckCircle2 className="w-5 h-5 shrink-0" />
                <span>Абсолютно верно! (✓)</span>
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
              className="flex flex-col gap-2 bg-destructive/10 border border-destructive/20 p-3.5 rounded-lg text-sm mt-4"
            >
              <div className="flex items-center gap-2 text-destructive font-medium">
                <XCircle className="w-5 h-5 shrink-0" />
                <span>Неверный ответ. (✗)</span>
              </div>
              {attempts >= 3 && (
                <div className="mt-2 pt-2 border-t border-destructive/20">
                  <div className="text-muted-foreground mb-3">
                    Правильный ответ: <span className="font-semibold text-foreground ml-1">
                      {Array.isArray(correct_answer) ? correct_answer[0] : correct_answer}
                    </span>
                  </div>
                  <div className="p-3 bg-background rounded border text-foreground text-sm">
                    <span className="font-semibold block mb-1">Объяснение:</span>
                    <div className="whitespace-pre-wrap">{parseMathText(explanation)}</div>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </form>
    </div>
  );
}
