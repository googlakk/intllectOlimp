import { Sparkles, UserRound } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { getAvatarCueAsset } from '@/lib/api/avatar';
import type { AvatarCue } from '@/lib/api/types';
import { useProtectedMediaUrl } from '@/lib/useProtectedMediaUrl';
import { activeNarrationSentence, narrationSegments, narrationSpeechText } from './avatarNarration';

type NarratorState = 'ready' | 'speaking' | 'paused' | 'completed';

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
  const videoRef = useRef<HTMLVideoElement>(null);
  const playbackTokenRef = useRef(0);
  const speechSegmentRef = useRef(0);
  const [narratorState, setNarratorState] = useState<NarratorState>('ready');
  const [progress, setProgress] = useState(0);
  const [showHint, setShowHint] = useState(true);
  const [videoRequested, setVideoRequested] = useState(false);
  const [pendingVideoPlay, setPendingVideoPlay] = useState(false);
  const [lazyVideoUrl, setLazyVideoUrl] = useState<string | undefined>(cue?.video_url);
  const [lazyPosterUrl, setLazyPosterUrl] = useState<string | undefined | null>(cue?.poster_url);
  const [assetLookupDone, setAssetLookupDone] = useState(Boolean(cue?.video_url));
  const narration = narrationSpeechText(cue?.fallback_text || cue?.script || '');
  const effectiveVideoUrl = lazyVideoUrl || cue?.video_url;
  const protectedVideo = useProtectedMediaUrl(effectiveVideoUrl, { enabled: videoRequested && Boolean(effectiveVideoUrl) });
  const speechSegments = useMemo(() => narrationSegments(cue?.script || ''), [cue?.script]);
  const activeSentence = useMemo(
    () => activeNarrationSentence(narration, progress),
    [narration, progress],
  );

  useEffect(() => () => {
    window.speechSynthesis?.cancel();
  }, []);

  useEffect(() => {
    playbackTokenRef.current += 1;
    window.speechSynthesis?.cancel();
    setNarratorState('ready');
    setProgress(0);
    speechSegmentRef.current = 0;
    setShowHint(true);
    setVideoRequested(false);
    setPendingVideoPlay(false);
    setLazyVideoUrl(cue?.video_url);
    setLazyPosterUrl(cue?.poster_url);
    setAssetLookupDone(Boolean(cue?.video_url));
    const hintTimer = window.setTimeout(() => setShowHint(false), 4500);
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
      videoRef.current.load();
    }
    return () => window.clearTimeout(hintTimer);
  }, [cue?.id, cue?.beat_id, cue?.video_url, cue?.poster_url]);

  useEffect(() => {
    if (!pendingVideoPlay || !protectedVideo.url || !videoRef.current) return;
    videoRef.current.muted = false;
    void videoRef.current.play()
      .then(() => {
        setPendingVideoPlay(false);
        setNarratorState('speaking');
      })
      .catch(() => {
        setPendingVideoPlay(false);
        setNarratorState('paused');
      });
  }, [pendingVideoPlay, protectedVideo.url]);

  if (!cue) return null;

  const pause = () => {
    playbackTokenRef.current += 1;
    window.speechSynthesis?.cancel();
    videoRef.current?.pause();
    setNarratorState('paused');
  };

  const speakFallback = () => {
    if (!avatarEnabled || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const token = ++playbackTokenRef.current;
    if (narratorState === 'completed') speechSegmentRef.current = 0;
    const speakNext = () => {
      if (playbackTokenRef.current !== token) return;
      const segmentIndex = speechSegmentRef.current;
      const segment = speechSegments[segmentIndex];
      if (!segment) {
        setProgress(1);
        setNarratorState('completed');
        speechSegmentRef.current = 0;
        return;
      }
      const utterance = new SpeechSynthesisUtterance(segment);
      utterance.lang = 'ru-RU';
      utterance.rate = 0.95;
      utterance.onboundary = (event) => {
        if (playbackTokenRef.current !== token) return;
        const localProgress = segment.length > 0 ? event.charIndex / segment.length : 0;
        setProgress(Math.min((segmentIndex + localProgress) / speechSegments.length, 0.99));
      };
      utterance.onend = () => {
        if (playbackTokenRef.current !== token) return;
        speechSegmentRef.current += 1;
        speakNext();
      };
      utterance.onerror = () => {
        if (playbackTokenRef.current === token) setNarratorState('paused');
      };
      window.speechSynthesis.speak(utterance);
    };
    speakNext();
    setNarratorState('speaking');
  };

  const play = async () => {
    setShowHint(false);
    if (!audioEnabled) onAudioEnabledChange(true);
    if (!effectiveVideoUrl && !assetLookupDone && lessonVersionId && cue?.id) {
      setAssetLookupDone(true);
      try {
        const asset = await getAvatarCueAsset({
          lessonVersionId,
          cueId: cue.id,
          sceneId: cue.scene_id,
        });
        if (asset?.video_url) {
          setLazyVideoUrl(asset.video_url);
          setLazyPosterUrl(asset.poster_url);
          setVideoRequested(true);
          setPendingVideoPlay(true);
          setNarratorState('paused');
          return;
        }
      } catch {
        // If generated video is not reachable, browser speech still explains the cue.
      }
    }
    if (effectiveVideoUrl && !protectedVideo.url && !protectedVideo.error) {
      setVideoRequested(true);
      setPendingVideoPlay(true);
      setNarratorState('paused');
      return;
    }
    if (!protectedVideo.url || !videoRef.current) {
      speakFallback();
      return;
    }
    if (narratorState === 'completed') {
      videoRef.current.currentTime = 0;
      setProgress(0);
    }
    videoRef.current.muted = false;
    try {
      await videoRef.current.play();
      setNarratorState('speaking');
    } catch {
      setNarratorState('paused');
    }
  };

  const toggleNarration = () => {
    if (narratorState === 'speaking') pause();
    else void play();
  };

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
        {protectedVideo.url ? (
          <div className={`absolute inset-0 transition-transform duration-[2500ms] ${isSpeaking ? 'scale-[1.02]' : 'scale-100'}`}>
            <span className="pointer-events-none absolute inset-[8%] rounded-[42%] bg-primary/10 blur-2xl" />
            <video
              ref={videoRef}
              src={protectedVideo.url}
              poster={lazyPosterUrl || cue.poster_url}
              playsInline
              preload="metadata"
              muted={!audioEnabled}
              onPlay={() => { setNarratorState('speaking'); }}
              onPause={() => setNarratorState((current) => current === 'speaking' ? 'paused' : current)}
              onEnded={() => { setProgress(1); setNarratorState('completed'); }}
              onTimeUpdate={(event) => {
                const video = event.currentTarget;
                if (Number.isFinite(video.duration) && video.duration > 0) setProgress(video.currentTime / video.duration);
              }}
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
