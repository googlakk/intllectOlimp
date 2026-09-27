import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Focus } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import DOMPurify from 'dompurify';
import { useProtectedMediaUrl } from '@/lib/useProtectedMediaUrl';
import { RichText } from './RichText';

export interface PresentationSlide {
  id?: string;
  heading: string;
  body: string;
  learning_point?: string;
  avatar_script?: string;
  visual?: string;
  media?: {
    kind: 'image' | 'video';
    url: string;
    poster_url?: string;
    alt_text?: string;
    caption?: string;
    media_slot_id?: string;
    pedagogical_role?: string;
  };
  media_slot?: {
    id: string;
    role: string;
    placement: string;
    learning_purpose: string;
    must_show?: string[];
    must_not_show?: string[];
  };
}

export interface PresentationProps {
  title: string;
  slides: PresentationSlide[];
  activeBeatId?: string;
  onTeachingBeatChange?: (beatId: string) => void;
}

export default function Presentation({ title, slides, activeBeatId, onTeachingBeatChange }: PresentationProps) {
  const slideIds = useMemo(() => slides.map((slide, index) => slide.id || `slide-${index + 1}`), [slides]);
  const requestedIndex = activeBeatId ? slideIds.indexOf(activeBeatId) : -1;
  const [currentIndex, setCurrentIndex] = useState(requestedIndex >= 0 ? requestedIndex : 0);
  const [videoRequested, setVideoRequested] = useState(false);
  const currentVideoSource = slides[currentIndex]?.media?.kind === 'video' ? slides[currentIndex]?.media?.url : '';
  const protectedVideo = useProtectedMediaUrl(currentVideoSource, { enabled: videoRequested });
  const videoUrl = protectedVideo.url || (!currentVideoSource?.startsWith('/api/') ? currentVideoSource : '');

  useEffect(() => {
    if (requestedIndex >= 0 && requestedIndex !== currentIndex) setCurrentIndex(requestedIndex);
  }, [activeBeatId, currentIndex, requestedIndex]);

  useEffect(() => {
    setVideoRequested(false);
  }, [currentIndex]);

  const selectSlide = (index: number) => {
    setCurrentIndex(index);
    const beatId = slideIds[index];
    if (beatId) onTeachingBeatChange?.(beatId);
  };

  if (!slides || slides.length === 0) return null;

  const nextSlide = () => {
    if (currentIndex < slides.length - 1) {
      selectSlide(currentIndex + 1);
    }
  };

  const prevSlide = () => {
    if (currentIndex > 0) {
      selectSlide(currentIndex - 1);
    }
  };

  const slide = slides[currentIndex];
  const visual = slide.media?.url || slide.visual?.trim() || '';
  const isSvg = visual.toLowerCase().startsWith('<svg');
  const isImageUrl = /^(?:https?:\/\/|data:image\/|\/)/i.test(visual);
  const cleanSvg = isSvg ? DOMPurify.sanitize(slide.visual!, { USE_PROFILES: { svg: true } }) : '';

  return (
    <div className="my-8 overflow-hidden rounded-lg border bg-card shadow-md">
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
            <div className={`w-full ${visual ? 'md:w-1/2' : ''} space-y-6`}>
              <h2 className="text-2xl md:text-3xl font-bold text-foreground leading-tight">
                <RichText text={slide.heading} inline />
              </h2>
              <div className="text-lg text-muted-foreground leading-relaxed whitespace-pre-wrap">
                <RichText text={slide.body} />
              </div>
            </div>
            
            {visual && (
              <div className="w-full md:w-1/2 flex justify-center items-center rounded-xl overflow-hidden">
                {slide.media?.kind === 'video' ? (
                  <figure className="w-full">
                    {!videoRequested ? (
                      <button
                        type="button"
                        onClick={() => setVideoRequested(true)}
                        className="group relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-lg bg-black text-background"
                        aria-label={`Смотреть видео: ${slide.heading}`}
                      >
                        {slide.media.poster_url ? (
                          <img
                            src={slide.media.poster_url}
                            alt=""
                            className="absolute inset-0 h-full w-full object-cover opacity-80 transition-transform duration-500 group-hover:scale-[1.02]"
                            loading="lazy"
                            decoding="async"
                          />
                        ) : (
                          <span className="absolute inset-0 bg-muted/40" />
                        )}
                        <span className="relative flex h-14 w-14 items-center justify-center rounded-full bg-background/95 text-primary shadow-lg transition-transform group-hover:scale-105">
                          <ChevronRight className="h-8 w-8" />
                        </span>
                      </button>
                    ) : protectedVideo.isLoading ? (
                      <div className="flex aspect-video w-full items-center justify-center rounded-lg bg-muted/20 text-sm font-medium text-muted-foreground">
                        Видео загружается...
                      </div>
                    ) : (
                      <video
                        src={videoUrl || undefined}
                        poster={slide.media.poster_url}
                        controls
                        playsInline
                        preload="metadata"
                        className="aspect-video w-full rounded-lg bg-black object-contain"
                      />
                    )}
                    {slide.media.caption && <figcaption className="mt-2 text-sm text-muted-foreground">{slide.media.caption}</figcaption>}
                  </figure>
                ) : isSvg ? (
                  <div dangerouslySetInnerHTML={{ __html: cleanSvg }} className="max-w-full" />
                ) : isImageUrl ? (
                  <div className="aspect-[7/4] w-full overflow-hidden rounded-lg bg-muted/20">
                    <img
                      src={visual}
                      alt={slide.media?.alt_text || slide.heading}
                      className="h-full w-full object-contain"
                      loading="lazy"
                      decoding="async"
                    />
                  </div>
                ) : (
                  <div className="w-full rounded-lg border border-primary/20 bg-primary/5 p-5 text-foreground">
                    <Focus className="mb-3 h-6 w-6 text-primary" />
                    <p className="text-sm font-bold uppercase text-primary">Обрати внимание</p>
                    <RichText text={visual} className="mt-2 text-base leading-relaxed" />
                  </div>
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
        
        <div className="flex">
          {slides.map((_, i) => (
            // Точка маленькая, а зона нажатия — под палец (32 px).
            <button
              key={i}
              onClick={() => selectSlide(i)}
              className="group flex h-8 w-6 items-center justify-center"
              aria-label={`Перейти к слайду ${i + 1}`}
            >
              <span className={`block h-2.5 w-2.5 rounded-full transition-colors ${
                currentIndex === i ? 'bg-primary' : 'bg-border group-hover:bg-primary/50'
              }`} />
            </button>
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
