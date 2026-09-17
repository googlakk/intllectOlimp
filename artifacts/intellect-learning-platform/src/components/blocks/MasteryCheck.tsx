import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, XCircle, Trophy } from 'lucide-react';
import { parseMathText } from './ShortExplanation';

export interface MasteryCheckQuestion {
  question: string;
  type: 'multiple_choice' | 'numeric';
  options?: string[];
  correct_answer: string;
  explanation: string;
  dimension: string;
}

export interface MasteryCheckProps {
  questions: MasteryCheckQuestion[];
  onAnswer?: (isCorrect: boolean) => void;
}

export default function MasteryCheck({ questions, onAnswer }: MasteryCheckProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<number, boolean>>({});
  const [showExplanation, setShowExplanation] = useState(false);
  const [currentValue, setCurrentValue] = useState('');
  
  if (!questions || questions.length === 0) return null;

  const currentQ = questions[currentIndex];
  const isFinished = currentIndex >= questions.length;

  const getLevel = (percentage: number) => {
    if (percentage <= 40) return "Начинающий";
    if (percentage <= 65) return "Развивающийся";
    if (percentage <= 85) return "Уверенный";
    return "Мастер";
  };

  const getLevelColor = (percentage: number) => {
    if (percentage <= 40) return "text-orange-500";
    if (percentage <= 65) return "text-blue-500";
    if (percentage <= 85) return "text-indigo-500";
    return "text-green-500";
  };

  const handleSubmit = (value: string) => {
    if (showExplanation) return;
    
    let isCorrect = false;
    const normVal = value.trim().toLowerCase().replace(/\s+/g, ' ');
    const normCorrect = currentQ.correct_answer.trim().toLowerCase().replace(/\s+/g, ' ');
    
    isCorrect = normVal === normCorrect;
    
    setAnswers(prev => ({ ...prev, [currentIndex]: isCorrect }));
    setShowExplanation(true);
  };

  const handleNext = () => {
    setCurrentValue('');
    setShowExplanation(false);
    
    if (currentIndex === questions.length - 1) {
      // Calculate final score
      const correctCount = Object.values(answers).filter(Boolean).length;
      const percentage = (correctCount / questions.length) * 100;
      onAnswer?.(percentage >= 66);
    }
    
    setCurrentIndex(prev => prev + 1);
  };

  if (isFinished) {
    const correctCount = Object.values(answers).filter(Boolean).length;
    const percentage = Math.round((correctCount / questions.length) * 100);
    const level = getLevel(percentage);
    const colorClass = getLevelColor(percentage);

    return (
      <div className="border rounded-2xl p-8 my-8 bg-card shadow-sm text-center">
        <Trophy className={`w-16 h-16 mx-auto mb-6 ${colorClass}`} />
        <h3 className="text-2xl font-bold text-foreground mb-2">Проверка завершена</h3>
        <p className="text-muted-foreground mb-6">Ваш результат: {correctCount} из {questions.length} ({percentage}%)</p>
        
        <div className="inline-block p-4 rounded-xl bg-muted/30 border mb-8">
          <span className="block text-sm text-muted-foreground mb-1 uppercase tracking-wider font-semibold">Ваш уровень</span>
          <span className={`text-3xl font-black ${colorClass}`}>{level}</span>
        </div>
      </div>
    );
  }

  const isCorrect = answers[currentIndex];
  const progress = (currentIndex / questions.length) * 100;

  return (
    <div className="border rounded-2xl overflow-hidden my-8 shadow-sm bg-card">
      {/* Progress Bar */}
      <div className="h-2 bg-muted w-full">
        <div 
          className="h-full bg-primary transition-all duration-500 ease-in-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="p-6 md:p-8">
        <div className="flex justify-between items-center mb-6">
          <span className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">
            Вопрос {currentIndex + 1} из {questions.length}
          </span>
          <span className="text-xs px-2.5 py-1 bg-secondary/20 text-secondary-foreground font-medium rounded-full">
            {currentQ.dimension}
          </span>
        </div>

        <h3 className="text-xl font-medium text-foreground mb-8 whitespace-pre-wrap">
          {parseMathText(currentQ.question)}
        </h3>

        <div className="space-y-4">
          {currentQ.type === 'multiple_choice' && currentQ.options ? (
            <div className="space-y-3">
              {currentQ.options.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => handleSubmit(opt)}
                  disabled={showExplanation}
                  className={`w-full text-left px-5 py-4 border rounded-xl text-base transition-all ${
                    showExplanation 
                      ? (opt === currentQ.correct_answer 
                          ? 'bg-green-50 border-green-500 dark:bg-green-900/30 dark:border-green-400' 
                          : 'bg-background opacity-50')
                      : 'bg-background hover:border-primary hover:bg-primary/5 focus:outline-none focus:ring-2 focus:ring-primary shadow-sm'
                  }`}
                >
                  {parseMathText(opt)}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="number"
                value={currentValue}
                onChange={(e) => setCurrentValue(e.target.value)}
                disabled={showExplanation}
                placeholder="Введите число..."
                className="flex-1 px-5 py-4 border rounded-xl bg-background text-lg focus:outline-none focus:ring-2 focus:ring-primary shadow-sm disabled:opacity-50"
              />
              <button
                onClick={() => handleSubmit(currentValue)}
                disabled={showExplanation || !currentValue.trim()}
                className="px-8 py-4 bg-primary text-primary-foreground rounded-xl font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors shadow-sm"
              >
                Ответить
              </button>
            </div>
          )}
        </div>

        <AnimatePresence>
          {showExplanation && (
            <motion.div
              initial={{ opacity: 0, height: 0, marginTop: 0 }}
              animate={{ opacity: 1, height: 'auto', marginTop: 32 }}
              className="overflow-hidden"
            >
              <div className={`p-5 rounded-xl border ${isCorrect ? 'bg-green-500/10 border-green-500/20' : 'bg-destructive/10 border-destructive/20'}`}>
                <div className={`flex items-center gap-2 font-medium mb-3 ${isCorrect ? 'text-green-700 dark:text-green-400' : 'text-destructive'}`}>
                  {isCorrect ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
                  {isCorrect ? 'Абсолютно верно! (✓)' : 'Неверно. (✗)'}
                </div>
                
                {!isCorrect && currentQ.type === 'numeric' && (
                  <div className="mb-3 text-sm text-foreground">
                    Правильный ответ: <span className="font-bold">{parseMathText(currentQ.correct_answer)}</span>
                  </div>
                )}
                
                <div className="text-sm text-foreground">
                  <span className="font-semibold block mb-1">Объяснение:</span>
                  <div className="whitespace-pre-wrap">{parseMathText(currentQ.explanation)}</div>
                </div>
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={handleNext}
                  className="px-6 py-2.5 bg-foreground text-background rounded-lg font-medium hover:bg-foreground/90 transition-colors shadow-sm"
                >
                  {currentIndex === questions.length - 1 ? 'Завершить проверку' : 'Следующий вопрос'}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
