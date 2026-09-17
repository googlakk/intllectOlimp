import React, { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import DOMPurify from 'dompurify';
import { parseMathText } from './ShortExplanation';

export interface PresentationSlide {
  heading: string;
  body: string;
  visual?: string;
}

export interface PresentationProps {
  title: string;
  slides: PresentationSlide[];
}

export default function Presentation({ title, slides }: PresentationProps) {
  const [currentIndex, setCurrentIndex] = useState(0);

  if (!slides || slides.length === 0) return null;

  const nextSlide = () => {
    if (currentIndex < slides.length - 1) {
      setCurrentIndex(prev => prev + 1);
    }
  };

  const prevSlide = () => {
    if (currentIndex > 0) {
      setCurrentIndex(prev => prev - 1);
    }
  };

  const slide = slides[currentIndex];
  
  const isSvg = slide.visual && slide.visual.trim().toLowerCase().startsWith('<svg');
  const cleanSvg = isSvg ? DOMPurify.sanitize(slide.visual!, { USE_PROFILES: { svg: true } }) : '';

  return (
    <div className="border rounded-2xl overflow-hidden my-8 shadow-md bg-card">
      {/* Header */}
      <div className="bg-primary text-primary-foreground p-4 flex justify-between items-center">
        <h3 className="font-semibold text-lg truncate pr-4">{title}</h3>
        <div className="text-sm font-medium bg-black/20 px-3 py-1 rounded-full whitespace-nowrap">
          {currentIndex + 1} / {slides.length}
        </div>
      </div>

      {/* Slide Content */}
      <div className="relative overflow-hidden min-h-[400px] flex items-center bg-background">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentIndex}
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -50 }}
            transition={{ duration: 0.3 }}
            className="w-full p-8 md:p-12 flex flex-col md:flex-row gap-8 items-center"
          >
            <div className={`w-full ${slide.visual ? 'md:w-1/2' : ''} space-y-6`}>
              <h2 className="text-2xl md:text-3xl font-bold text-foreground leading-tight">
                {parseMathText(slide.heading)}
              </h2>
              <div className="text-lg text-muted-foreground leading-relaxed whitespace-pre-wrap">
                {parseMathText(slide.body)}
              </div>
            </div>
            
            {slide.visual && (
              <div className="w-full md:w-1/2 flex justify-center items-center rounded-xl overflow-hidden">
                {isSvg ? (
                  <div dangerouslySetInnerHTML={{ __html: cleanSvg }} className="max-w-full" />
                ) : (
                  <img src={slide.visual} alt={slide.heading} className="max-w-full max-h-[300px] object-contain rounded-lg" />
                )}
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Controls */}
      <div className="bg-muted/30 border-t p-4 flex justify-between items-center">
        <button
          onClick={prevSlide}
          disabled={currentIndex === 0}
          aria-label="Предыдущий слайд"
          className="flex items-center gap-2 px-4 py-2 bg-background border rounded-lg font-medium text-foreground hover:bg-muted disabled:opacity-50 disabled:pointer-events-none transition-colors"
        >
          <ChevronLeft className="w-5 h-5" />
          <span className="hidden sm:inline">Назад</span>
        </button>
        
        <div className="flex gap-1">
          {slides.map((_, i) => (
            <button
              key={i}
              onClick={() => setCurrentIndex(i)}
              className={`w-2.5 h-2.5 rounded-full transition-colors ${
                currentIndex === i ? 'bg-primary' : 'bg-border hover:bg-primary/50'
              }`}
              aria-label={`Перейти к слайду ${i + 1}`}
            />
          ))}
        </div>

        <button
          onClick={nextSlide}
          disabled={currentIndex === slides.length - 1}
          aria-label="Следующий слайд"
          className="flex items-center gap-2 px-4 py-2 bg-background border rounded-lg font-medium text-foreground hover:bg-muted disabled:opacity-50 disabled:pointer-events-none transition-colors"
        >
          <span className="hidden sm:inline">Вперед</span>
          <ChevronRight className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
