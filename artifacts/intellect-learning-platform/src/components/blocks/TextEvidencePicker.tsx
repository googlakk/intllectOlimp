import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, XCircle } from 'lucide-react';
import { parseMathText } from './ShortExplanation';

export interface TextEvidencePickerProps {
  passage: string;
  claim: string;
  correct_segments: string[];
  explanation: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function TextEvidencePicker({ passage, claim, correct_segments, explanation, onAnswer }: TextEvidencePickerProps) {
  const [selected, setSelected] = useState<number[]>([]);
  const [submitted, setSubmitted] = useState(false);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);

  const sentences = useMemo(() => {
    const matches = passage.match(/[^.!?]+[.!?]*/g);
    return matches ? matches.map(s => s.trim()).filter(Boolean) : [passage.trim()];
  }, [passage]);

  const toggleSelect = (index: number) => {
    if (submitted) return;
    setSelected(prev => 
      prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]
    );
  };

  const normalizeText = (text: string) => text.toLowerCase().replace(/\s+/g, ' ').trim();

  const correctIndices = useMemo(() => {
    return sentences.map((sentence, i) => {
      const normSentence = normalizeText(sentence);
      const isCorrectMatch = correct_segments.some(segment => {
        const normSegment = normalizeText(segment);
        return normSentence.includes(normSegment) || normSegment.includes(normSentence);
      });
      return isCorrectMatch ? i : -1;
    }).filter(i => i !== -1);
  }, [sentences, correct_segments]);

  const handleSubmit = () => {
    if (selected.length === 0) return;
    
    setSubmitted(true);
    
    const allSelectedCorrect = selected.every(i => correctIndices.includes(i));
    const allCorrectSelected = correctIndices.every(i => selected.includes(i));
    const correct = allSelectedCorrect && allCorrectSelected;
    
    setIsCorrect(correct);
    onAnswer?.(correct);
  };

  return (
    <div className="border rounded-xl p-6 my-6 bg-card shadow-sm">
      <div className="mb-6">
        <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-primary"></span>
          Поиск доказательств в тексте
        </h3>
        <div className="bg-primary/5 border border-primary/20 rounded-lg p-4 mb-4">
          <span className="text-xs font-semibold text-primary uppercase tracking-wider mb-1 block">Утверждение:</span>
          <p className="text-foreground font-medium">{parseMathText(claim)}</p>
        </div>
        <p className="text-sm text-muted-foreground mb-4">
          Выберите предложения в тексте, которые подтверждают данное утверждение.
        </p>
      </div>

      <div className="p-5 bg-background rounded-lg border leading-relaxed text-base mb-6">
        {sentences.map((sentence, index) => {
          const isSelected = selected.includes(index);
          const isActuallyCorrect = correctIndices.includes(index);
          
          let btnClass = "inline transition-colors duration-200 cursor-pointer rounded px-1 -mx-1 ";
          
          if (!submitted) {
            btnClass += isSelected ? "bg-primary/20 text-primary-foreground underline decoration-primary underline-offset-4" : "hover:bg-muted";
          } else {
            if (isSelected && isActuallyCorrect) {
              btnClass += "bg-green-500/30 text-green-900 dark:text-green-100 font-medium underline decoration-green-500 underline-offset-4";
            } else if (isSelected && !isActuallyCorrect) {
              btnClass += "bg-red-500/30 text-red-900 dark:text-red-100 line-through decoration-red-500";
            } else if (!isSelected && isActuallyCorrect) {
              btnClass += "bg-green-500/10 underline decoration-green-500/50 underline-offset-4 decoration-dashed";
            }
          }

          return (
            <React.Fragment key={index}>
              <span 
                onClick={() => toggleSelect(index)}
                className={btnClass}
              >
                {sentence}
              </span>
              {' '}
            </React.Fragment>
          );
        })}
      </div>

      {!submitted ? (
        <button
          onClick={handleSubmit}
          disabled={selected.length === 0}
          className="px-6 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
        >
          Проверить ответ
        </button>
      ) : (
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-6 space-y-4"
          >
            {isCorrect ? (
              <div className="flex items-center gap-2 text-green-700 dark:text-green-400 text-sm font-medium bg-green-500/10 border border-green-500/20 p-3.5 rounded-lg">
                <CheckCircle2 className="w-5 h-5 shrink-0" />
                <span>Отлично! Вы нашли все правильные подтверждения. </span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-destructive text-sm font-medium bg-destructive/10 border border-destructive/20 p-3.5 rounded-lg">
                <XCircle className="w-5 h-5 shrink-0" />
                <span>Не совсем так. Ознакомьтесь с правильным выбором (отмечен зеленым). </span>
              </div>
            )}
            
            <div className="p-4 bg-muted/30 border rounded-lg text-sm text-foreground">
              <span className="font-semibold block mb-2">Объяснение:</span>
              <div className="whitespace-pre-wrap">{parseMathText(explanation)}</div>
            </div>
          </motion.div>
        </AnimatePresence>
      )}
    </div>
  );
}
