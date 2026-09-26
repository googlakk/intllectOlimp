import { Sparkles, UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';
import type { AvatarCue } from '@/lib/api/types';
import { useAvatarNarration } from './useAvatarNarration';

type AvatarCompanionProps = {
  cue?: AvatarCue;
  previewImageUrl?: string | null;
  companionName?: string;
  lessonVersionId?: number | null;
  avatarEnabled: boolean;
  audioEnabled: boolean;
  onAvatarEnabledChange: (enabled: boolean) => void;
  onAudioEnabledChange: (enabled: boolean) => void;
};

/** Рассказчик крупно — превью аватара в редакторе урока. В уроке ученика аватар живёт в плашке помощника. */
export function AvatarCompanion({
  cue,
  previewImageUrl,
  companionName = 'Помощник',
  lessonVersionId,
  avatarEnabled,
  audioEnabled,
  onAvatarEnabledChange,
  onAudioEnabledChange,
}: AvatarCompanionProps) {
  const narration = useAvatarNarration({ cue, lessonVersionId, avatarEnabled, audioEnabled, onAudioEnabledChange });
  const [showHint, setShowHint] = useState(true);
  useEffect(() => {
    setShowHint(true);
    const timer = window.setTimeout(() => setShowHint(false), 4500);
    return () => window.clearTimeout(timer);
  }, [cue?.id, cue?.beat_id]);

  if (!cue) return null;
  const narratorState = narration.state;
  const activeSentence = narration.activeSentence;
  const toggleNarration = () => { setShowHint(false); narration.toggle(); };

  if (!avatarEnabled) {
    return (
      <button type="button" onClick={() => onAvatarEnabledChange(true)} className="pointer-events-auto relative h-16 w-16 overflow-hidden rounded-full drop-shadow-xl" aria-label="Показать рассказчика">
        {previewImageUrl ? <img src={previewImageUrl} alt="" className="h-full w-full object-cover object-top" /> : <UserRound className="m-auto h-10 w-10 text-primary" />}
      </button>
    );
  }

  const isSpeaking = narratorState === 'speaking';
  const interactionLabel = isSpeaking
    ? `Поставить ${companionName} на паузу`
    : narratorState === 'completed'
      ? `Повторить объяснение ${companionName}`
      : `Запустить объяснение ${companionName}`;

  return (
    <aside className="pointer-events-none relative flex w-full flex-col items-center justify-end" aria-label="Интерактивный рассказчик урока">
      {(isSpeaking || narratorState === 'paused') && activeSentence && (
        <div className="pointer-events-none relative z-20 mb-1 max-w-[280px] rounded-lg bg-foreground/90 px-3 py-2 text-center text-xs font-medium leading-relaxed text-background shadow-lg backdrop-blur-sm">
          {activeSentence}
          <span className="absolute left-1/2 top-full h-0 w-0 -translate-x-1/2 border-x-[7px] border-t-[7px] border-x-transparent border-t-foreground/90" />
        </div>
      )}

      <button
        type="button"
        onClick={toggleNarration}
        aria-label={interactionLabel}
        title={isSpeaking ? 'Нажмите, чтобы поставить на паузу' : 'Нажмите, чтобы услышать объяснение'}
        className="pointer-events-auto group relative h-[clamp(180px,30vh,300px)] w-[clamp(150px,22vw,250px)] overflow-visible outline-none"
      >
        {narration.video ? (
          <div className={`absolute inset-0 transition-transform duration-[2500ms] ${isSpeaking ? 'scale-[1.02]' : 'scale-100'}`}>
            <span className="pointer-events-none absolute inset-[8%] rounded-[42%] bg-primary/10 blur-2xl" />
            <video
              ref={narration.video.ref}
              src={narration.video.src}
              poster={narration.video.poster}
              playsInline
              preload="metadata"
              muted={narration.video.muted}
              onPlay={narration.video.onPlay}
              onPause={narration.video.onPause}
              onEnded={narration.video.onEnded}
              onTimeUpdate={narration.video.onTimeUpdate}
              className="absolute left-1/2 top-0 h-full w-auto max-w-none -translate-x-1/2 object-cover drop-shadow-[0_18px_18px_rgba(15,23,42,0.24)] [mask-image:radial-gradient(ellipse_58%_68%_at_50%_48%,black_62%,rgba(0,0,0,0.82)_72%,rgba(0,0,0,0.28)_86%,transparent_100%)] [-webkit-mask-image:radial-gradient(ellipse_58%_68%_at_50%_48%,black_62%,rgba(0,0,0,0.82)_72%,rgba(0,0,0,0.28)_86%,transparent_100%)]"
            />
          </div>
        ) : previewImageUrl ? (
          <img src={previewImageUrl} alt="" loading="lazy" decoding="async" className={`absolute left-1/2 top-0 h-full w-auto max-w-none -translate-x-1/2 object-cover object-top drop-shadow-[0_14px_12px_rgba(15,23,42,0.24)] transition-transform duration-[2500ms] [mask-image:radial-gradient(ellipse_58%_68%_at_50%_48%,black_62%,rgba(0,0,0,0.82)_72%,rgba(0,0,0,0.28)_86%,transparent_100%)] [-webkit-mask-image:radial-gradient(ellipse_58%_68%_at_50%_48%,black_62%,rgba(0,0,0,0.82)_72%,rgba(0,0,0,0.28)_86%,transparent_100%)] ${isSpeaking ? 'scale-[1.025]' : 'scale-100'}`} />
        ) : (
          <UserRound className="m-auto h-24 w-24 text-primary drop-shadow-lg" />
        )}

        <span className={`absolute bottom-[8%] right-[17%] z-20 h-3 w-3 rounded-full border-2 border-background shadow-sm group-focus-visible:ring-2 group-focus-visible:ring-primary group-focus-visible:ring-offset-2 ${isSpeaking ? 'animate-pulse bg-green-500' : 'bg-primary'}`} />
        {isSpeaking && <Sparkles className="absolute right-[12%] top-[18%] z-20 h-5 w-5 animate-pulse text-primary drop-shadow" />}
      </button>

      {showHint && narratorState === 'ready' && (
        <div className="pointer-events-none -mt-3 rounded-full bg-foreground/85 px-3 py-1.5 text-[11px] font-semibold text-background shadow-md">
          Нажмите на рассказчика
        </div>
      )}
      <span className="sr-only" aria-live="polite">
        {isSpeaking ? `${companionName} объясняет` : narratorState === 'paused' ? 'Объяснение на паузе' : narratorState === 'completed' ? 'Объяснение завершено' : 'Рассказчик готов'}
      </span>
    </aside>
  );
}
