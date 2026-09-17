import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, XCircle } from 'lucide-react';
import { parseMathText } from './ShortExplanation';

export interface ArgumentBuilderProps {
  prompt: string;
  thesis_options: string[];
  evidence_pool: string[];
  correct_thesis: string;
  correct_evidence: string[];
  model_reasoning: string;
  onAnswer?: (isCorrect: boolean) => void;
}

export default function ArgumentBuilder({ 
  prompt, 
  thesis_options, 
  evidence_pool, 
  correct_thesis, 
  correct_evidence, 
  model_reasoning, 
  onAnswer 
}: ArgumentBuilderProps) {
  const [selectedThesis, setSelectedThesis] = useState<string>('');
  const [selectedEvidence, setSelectedEvidence] = useState<string[]>([]);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);

  const toggleEvidence = (ev: string) => {
    setSelectedEvidence(prev => 
      prev.includes(ev) ? prev.filter(item => item !== ev) : [...prev, ev]
    );
  };

  const normalize = (text: string) => text.toLowerCase().replace(/\s+/g, ' ').trim();

  const handleSubmit = () => {
    const isThesisCorrect = normalize(selectedThesis) === normalize(correct_thesis);
    const correctEvNorm = correct_evidence.map(normalize);
    const selectedEvNorm = selectedEvidence.map(normalize);
    
    const isEvidenceCorrect = 
      correctEvNorm.length === selectedEvNorm.length && 
      selectedEvNorm.every(ev => correctEvNorm.includes(ev));

    const overallCorrect = isThesisCorrect && isEvidenceCorrect;
    setIsCorrect(overallCorrect);
    setStep(3);
    onAnswer?.(overallCorrect);
  };

  return (
    <div className="border rounded-xl p-6 my-6 bg-card shadow-sm">
      <div className="mb-6">
        <h3 className="font-semibold text-lg mb-3 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-secondary"></span>
          Построение аргумента
        </h3>
        <div className="text-foreground p-4 bg-muted/20 rounded-lg whitespace-pre-wrap">
          {parseMathText(prompt)}
        </div>
      </div>

      <div className="space-y-8">
        {/* Step 1: Thesis */}
        <div className={`transition-opacity duration-300 ${step !== 1 && step !== 3 ? 'opacity-50 pointer-events-none' : ''}`}>
          <h4 className="font-medium text-foreground mb-3 flex items-center gap-2">
            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/20 text-primary text-xs font-bold">1</span>
            Выберите тезис
          </h4>
          <div className="space-y-2 pl-8">
            {thesis_options.map((thesis, i) => (
              <label 
                key={i}
                className={`flex items-start p-3 border rounded-lg cursor-pointer transition-colors ${
                  selectedThesis === thesis ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                } ${(step === 3) ? 'pointer-events-none' : ''}`}
              >
                <input
                  type="radio"
                  name="thesis"
                  value={thesis}
                  checked={selectedThesis === thesis}
                  onChange={() => {
                    setSelectedThesis(thesis);
                    if (step === 1) setStep(2);
                  }}
                  disabled={step === 3}
                  className="mt-1.5 mr-3 text-primary focus:ring-primary h-4 w-4"
                />
                <span className="text-sm text-foreground leading-relaxed">{parseMathText(thesis)}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Step 2: Evidence */}
        <div className={`transition-opacity duration-300 ${step < 2 ? 'opacity-30 pointer-events-none' : ''} ${step === 3 ? 'pointer-events-none' : ''}`}>
          <h4 className="font-medium text-foreground mb-3 flex items-center gap-2">
            <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/20 text-primary text-xs font-bold">2</span>
            Выберите доказательства
          </h4>
          <div className="space-y-2 pl-8">
            {evidence_pool.map((evidence, i) => (
              <label 
                key={i}
                className={`flex items-start p-3 border rounded-lg cursor-pointer transition-colors ${
                  selectedEvidence.includes(evidence) ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                } ${step === 3 ? 'pointer-events-none' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={selectedEvidence.includes(evidence)}
                  onChange={() => toggleEvidence(evidence)}
                  disabled={step === 3}
                  className="mt-1.5 mr-3 rounded text-primary focus:ring-primary h-4 w-4"
                />
                <span className="text-sm text-foreground leading-relaxed">{parseMathText(evidence)}</span>
              </label>
            ))}
          </div>
          
          {step === 2 && (
            <div className="mt-6 pl-8">
              <button
                onClick={handleSubmit}
                disabled={selectedEvidence.length === 0}
                className="px-6 py-2.5 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
              >
                Проверить аргументацию
              </button>
            </div>
          )}
        </div>

        {/* Step 3: Result */}
        <AnimatePresence>
          {step === 3 && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="pt-4 border-t"
            >
              <h4 className="font-medium text-foreground mb-4 flex items-center gap-2">
                <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/20 text-primary text-xs font-bold">3</span>
                Результат
              </h4>
              
              <div className="pl-8 space-y-4">
                {isCorrect ? (
                  <div className="flex items-center gap-2 text-green-700 dark:text-green-400 text-sm font-medium bg-green-500/10 border border-green-500/20 p-3.5 rounded-lg">
                    <CheckCircle2 className="w-5 h-5 shrink-0" />
                    <span>Блестяще! Вы построили сильный и точный аргумент. </span>
                  </div>
                ) : (
                  <div className="flex items-center gap-2 text-destructive text-sm font-medium bg-destructive/10 border border-destructive/20 p-3.5 rounded-lg">
                    <XCircle className="w-5 h-5 shrink-0" />
                    <span>Аргумент построен неверно. </span>
                  </div>
                )}

                <div className="p-5 bg-muted/30 border rounded-lg text-sm text-foreground">
                  <span className="font-semibold block mb-3 text-base">Идеальная модель аргумента:</span>
                  
                  <div className="mb-4">
                    <span className="text-xs font-semibold text-primary uppercase tracking-wider mb-1 block">Тезис:</span>
                    <p className="bg-background border rounded p-3">{parseMathText(correct_thesis)}</p>
                  </div>
                  
                  <div className="mb-4">
                    <span className="text-xs font-semibold text-primary uppercase tracking-wider mb-1 block">Доказательства:</span>
                    <ul className="list-disc pl-5 space-y-1.5">
                      {correct_evidence.map((ev, i) => (
                        <li key={i}>{parseMathText(ev)}</li>
                      ))}
                    </ul>
                  </div>

                  <div className="mt-6 pt-4 border-t border-border/50">
                    <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 block">Объяснение:</span>
                    <div className="whitespace-pre-wrap leading-relaxed">{parseMathText(model_reasoning)}</div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
