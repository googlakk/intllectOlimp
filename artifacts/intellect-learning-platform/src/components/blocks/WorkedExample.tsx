import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { parseMathText } from './ShortExplanation';
import { HelpCircle } from 'lucide-react';

export interface WorkedExampleStep {
  description: string;
  math?: string;
  hint?: string;
}

export interface WorkedExampleProps {
  problem: string;
  steps: WorkedExampleStep[];
  final_answer: string;
}

export default function WorkedExample({ problem, steps, final_answer }: WorkedExampleProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [activeHintIndex, setActiveHintIndex] = useState<number | null>(null);

  const handleNextStep = () => {
    if (currentStep < steps.length + 1) {
      setCurrentStep(prev => prev + 1);
      setActiveHintIndex(null);
    }
  };

  return (
    <div className="border rounded-xl p-6 my-6 bg-card shadow-sm">
      <h3 className="font-semibold text-lg mb-4 text-foreground">Пример решения</h3>
      <div className="mb-6 text-foreground p-4 bg-muted/30 rounded-lg whitespace-pre-wrap">
        <span className="font-medium mr-2 text-primary">Задача:</span>
        {parseMathText(problem)}
      </div>
      
      <div className="space-y-4 mb-6">
        <AnimatePresence initial={false}>
          {steps.map((step, index) => (
            index < currentStep && (
              <motion.div
                key={index}
                initial={{ opacity: 0, height: 0, x: -10 }}
                animate={{ opacity: 1, height: 'auto', x: 0 }}
                transition={{ duration: 0.3 }}
                className="pl-4 border-l-2 border-primary/30 py-2 overflow-hidden"
              >
                <span className="font-medium text-foreground text-sm block mb-1">Шаг {index + 1}</span>
                <div className="text-muted-foreground text-sm whitespace-pre-wrap mb-2">
                  {parseMathText(step.description)}
                </div>
                {step.math && (
                  <div className="my-2 p-3 bg-background rounded border text-center overflow-x-auto">
                    {parseMathText(step.math)}
                  </div>
                )}
                {step.hint && (
                  <div className="mt-2">
                    <button
                      onClick={() => setActiveHintIndex(activeHintIndex === index ? null : index)}
                      className="flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      <HelpCircle className="w-3.5 h-3.5" />
                      {activeHintIndex === index ? 'Скрыть подсказку' : 'Показать подсказку'}
                    </button>
                    <AnimatePresence>
                      {activeHintIndex === index && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="mt-2 overflow-hidden"
                        >
                          <div className="text-xs p-3 bg-primary/5 rounded border border-primary/10 text-muted-foreground italic">
                            {parseMathText(step.hint)}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                )}
              </motion.div>
            )
          ))}
        </AnimatePresence>

        <AnimatePresence>
          {currentStep >= steps.length && (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.4, type: "spring" }}
              className="mt-6 p-4 bg-green-500/10 border border-green-500/20 rounded-lg text-green-800 dark:text-green-300"
            >
              <span className="font-semibold mr-2 block mb-1">Ответ:</span>
              <div className="text-lg whitespace-pre-wrap">{parseMathText(final_answer)}</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {currentStep < steps.length && (
        <button
          onClick={handleNextStep}
          className="px-5 py-2.5 bg-secondary text-secondary-foreground rounded-lg text-sm font-medium hover:bg-secondary/80 transition-colors shadow-sm"
        >
          Показать следующий шаг
        </button>
      )}
    </div>
  );
}
