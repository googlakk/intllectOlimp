import { ImageIcon, PlayCircle } from 'lucide-react';
import { useState } from 'react';
import { useProtectedMediaUrl } from '@/lib/useProtectedMediaUrl';
import { parseMathText } from './ShortExplanation';

export interface GeneratedMediaProps {
  title: string;
  description?: string;
  media_kind: 'image' | 'video';
  url?: string;
  data_url?: string;
  poster_url?: string;
  alt_text?: string;
  caption?: string;
  pedagogical_role?: string;
  visual_intent?: string;
  success_check?: string;
  prompt?: string;
  model?: string;
}

export default function GeneratedMedia({
  title,
  description,
  media_kind,
  url,
  data_url,
  poster_url,
  alt_text,
  caption,
}: GeneratedMediaProps) {
  const shownTitle = title.replace(/^Визуализация к шагу:\s*/i, '');
  // Генератор часто повторяет заголовок в описании и подписи — показываем один раз.
  const same = (value?: string) => !value || value.trim().toLowerCase() === shownTitle.trim().toLowerCase();
  const shownDescription = same(description) ? '' : description;
  const shownCaption = same(caption) || caption === description ? '' : caption;
  const source = data_url || url || '';
  const [videoRequested, setVideoRequested] = useState(false);
  const protectedMedia = useProtectedMediaUrl(source, {
    enabled: media_kind === 'image' || videoRequested,
  });
  const mediaUrl = protectedMedia.url || (!source.startsWith('/api/') ? source : '');
  return (
    <div className="my-8 overflow-hidden rounded-xl border bg-card shadow-sm">
      <div className="border-b bg-muted/10 p-6">
        <div className="mb-2 flex items-center gap-2">
          {media_kind === 'image' ? <ImageIcon className="h-5 w-5 text-primary" /> : <PlayCircle className="h-5 w-5 text-primary" />}
          <h3 className="text-xl font-semibold text-foreground">{shownTitle}</h3>
        </div>
        {shownDescription && (
          <div className="text-sm leading-relaxed text-muted-foreground">
            {parseMathText(shownDescription)}
          </div>
        )}
      </div>

      <div className="bg-background p-4">
        {source ? (
          media_kind === 'image' ? (
            <img
              src={mediaUrl || undefined}
              alt={alt_text || shownTitle}
              className="mx-auto aspect-video max-h-[520px] w-full rounded-lg bg-muted/20 object-contain"
              loading="lazy"
              decoding="async"
            />
          ) : !videoRequested ? (
            <button
              type="button"
              onClick={() => setVideoRequested(true)}
              className="group relative flex aspect-video w-full items-center justify-center overflow-hidden rounded-lg bg-black text-background"
              aria-label={`Смотреть видео: ${shownTitle}`}
            >
              {poster_url ? (
                <img
                  src={poster_url}
                  alt=""
                  className="absolute inset-0 h-full w-full object-cover opacity-80 transition-transform duration-500 group-hover:scale-[1.02]"
                  loading="lazy"
                  decoding="async"
                />
              ) : (
                <span className="absolute inset-0 bg-muted/40" />
              )}
              <span className="relative flex h-16 w-16 items-center justify-center rounded-full bg-background/95 text-primary shadow-lg transition-transform group-hover:scale-105">
                <PlayCircle className="h-8 w-8" />
              </span>
            </button>
          ) : protectedMedia.isLoading ? (
            <div className="flex aspect-video items-center justify-center rounded-lg bg-muted/20 text-sm font-medium text-muted-foreground">
              Видео загружается...
            </div>
          ) : (
            <video
              src={mediaUrl || undefined}
              poster={poster_url}
              controls
              playsInline
              preload="metadata"
              className="mx-auto aspect-video w-full rounded-lg bg-black"
            />
          )
        ) : (
          <div className="flex aspect-video items-center justify-center rounded-lg border border-dashed bg-muted/20 text-sm font-medium text-muted-foreground">
            Медиа ещё генерируется
          </div>
        )}
      </div>

      {/* Роль, промпт и модель — служебные данные для учителя, ученику их не показываем. */}
      {shownCaption && (
        <div className="border-t bg-muted/20 p-4 text-center text-sm italic text-muted-foreground">
          {parseMathText(shownCaption)}
        </div>
      )}
    </div>
  );
}
