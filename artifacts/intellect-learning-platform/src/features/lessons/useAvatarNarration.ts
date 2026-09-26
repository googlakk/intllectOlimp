import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAvatarCueAssets } from '@/lib/api/avatar';
import type { AvatarCue } from '@/lib/api/types';
import { useProtectedMediaUrl } from '@/lib/useProtectedMediaUrl';
import { activeNarrationSentence, narrationSegments, narrationSpeechText } from './avatarNarration';

/** Видео заранее не подгружаем, если ученик экономит трафик или сеть медленная: загрузится по нажатию. */
function canPrefetchVideo(): boolean {
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
  if (!connection) return true;
  return !connection.saveData && !['slow-2g', '2g'].includes(connection.effectiveType ?? '');
}

export type NarratorState = 'ready' | 'speaking' | 'paused' | 'completed';

type Options = {
  cue?: AvatarCue;
  lessonVersionId?: number | null;
  avatarEnabled: boolean;
  audioEnabled: boolean;
  onAudioEnabledChange: (enabled: boolean) => void;
};

/**
 * Озвучка реплики аватара: видео (если сгенерировано) или синтез речи браузера,
 * с текущей фразой для подписи. Общая для плашки урока и превью в редакторе.
 * Ссылки на видео всех реплик приходят одним запросом при открытии урока — прямые (подписанные)
 * ссылки хранилища: <video> играет ролик по мере загрузки, без нашего сервера.
 * Пока видео готовится, голос браузера не включается — иначе звучат два рассказчика подряд.
 */
export function useAvatarNarration({ cue, lessonVersionId, avatarEnabled, audioEnabled, onAudioEnabledChange }: Options) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  // Элемент <video> появляется, когда раскрывается панель: запуск ждёт его, а не включает голос браузера.
  const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null);
  const attachVideo = useCallback((element: HTMLVideoElement | null) => {
    videoRef.current = element;
    setVideoElement(element);
  }, []);
  const playbackTokenRef = useRef(0);
  const speechSegmentRef = useRef(0);
  const [state, setState] = useState<NarratorState>('ready');
  const [progress, setProgress] = useState(0);
  const [videoRequested, setVideoRequested] = useState(false);
  const [pendingVideoPlay, setPendingVideoPlay] = useState(false);
  // Нажали «Послушать», пока ссылки на видео ещё не пришли: решим, когда придут.
  const wantsPlayRef = useRef(false);
  // Ссылка истекла (ноутбук спал) — один раз берём свежие ссылки, дальше голос браузера.
  const refreshedAfterErrorRef = useRef(false);
  const cueAssets = useAvatarCueAssets(lessonVersionId, avatarEnabled);
  const cueAsset = cue?.id ? cueAssets.data?.find((asset) => asset.cue_id === cue.id) : undefined;
  const effectiveVideoUrl = cueAsset?.video_url || cue?.video_url;
  const posterUrl = cueAsset?.poster_url || cue?.poster_url;
  const assetsLoading = avatarEnabled && Boolean(lessonVersionId) && cueAssets.isLoading;
  // Прямая ссылка отдаётся <video> как есть; старый адрес /api/… качается целиком только по нажатию.
  const protectedVideo = useProtectedMediaUrl(effectiveVideoUrl, { enabled: videoRequested && Boolean(effectiveVideoUrl) });
  const narration = narrationSpeechText(cue?.fallback_text || cue?.script || '');
  const speechSegments = useMemo(() => narrationSegments(cue?.script || ''), [cue?.script]);
  const activeSentence = useMemo(() => activeNarrationSentence(narration, progress), [narration, progress]);

  useEffect(() => () => { window.speechSynthesis?.cancel(); }, []);

  // Новая реплика — всё с начала.
  useEffect(() => {
    playbackTokenRef.current += 1;
    window.speechSynthesis?.cancel();
    setState('ready');
    setProgress(0);
    speechSegmentRef.current = 0;
    setVideoRequested(false);
    setPendingVideoPlay(false);
    wantsPlayRef.current = false;
    refreshedAfterErrorRef.current = false;
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
    }
  }, [cue?.id, cue?.beat_id]);

  // Ссылки пришли, а видео у этой реплики нет — объяснит голос браузера, если ученик уже ждёт.
  useEffect(() => {
    if (assetsLoading || !wantsPlayRef.current || effectiveVideoUrl) return;
    wantsPlayRef.current = false;
    setPendingVideoPlay(false);
    speakFallback();
  }, [assetsLoading, effectiveVideoUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  // Видео не загрузилось — тоже голос браузера.
  useEffect(() => {
    if (!protectedVideo.error || !wantsPlayRef.current) return;
    wantsPlayRef.current = false;
    setPendingVideoPlay(false);
    speakFallback();
  }, [protectedVideo.error]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!pendingVideoPlay || !protectedVideo.url || !videoElement) return;
    wantsPlayRef.current = false;
    window.speechSynthesis?.cancel();
    videoElement.muted = false;
    void videoElement.play()
      .then(() => { setPendingVideoPlay(false); setState('speaking'); })
      .catch(() => { setPendingVideoPlay(false); setState('paused'); });
  }, [pendingVideoPlay, protectedVideo.url, videoElement]);

  const pause = () => {
    playbackTokenRef.current += 1;
    wantsPlayRef.current = false;
    setPendingVideoPlay(false);  // видео не должно стартовать само, когда панель откроют снова
    window.speechSynthesis?.cancel();
    videoRef.current?.pause();
    setState('paused');
  };

  const speakFallback = () => {
    if (!avatarEnabled || !('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const token = ++playbackTokenRef.current;
    if (state === 'completed') speechSegmentRef.current = 0;
    const speakNext = () => {
      if (playbackTokenRef.current !== token) return;
      const segmentIndex = speechSegmentRef.current;
      const segment = speechSegments[segmentIndex];
      if (!segment) {
        setProgress(1);
        setState('completed');
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
      utterance.onerror = () => { if (playbackTokenRef.current === token) setState('paused'); };
      window.speechSynthesis.speak(utterance);
    };
    speakNext();
    setState('speaking');
  };

  const play = async () => {
    if (!audioEnabled) onAudioEnabledChange(true);
    const element = videoRef.current;
    const videoReady = Boolean(protectedVideo.url && element);
    if (!videoReady && (assetsLoading || effectiveVideoUrl) && !protectedVideo.error) {
      // Видео ещё готовится или панель только раскрывается — ждём его, без голоса браузера.
      wantsPlayRef.current = true;
      if (effectiveVideoUrl) setVideoRequested(true);
      setPendingVideoPlay(true);
      setState('paused');
      return;
    }
    if (!videoReady || !element) {
      speakFallback();
      return;
    }
    if (state === 'completed') {
      element.currentTime = 0;
      setProgress(0);
    }
    window.speechSynthesis?.cancel();
    element.muted = false;
    try {
      await element.play();
      setState('speaking');
    } catch {
      setState('paused');
    }
  };

  // Повторное нажатие во время загрузки отменяет ожидание.
  const toggle = () => { if (state === 'speaking' || (pendingVideoPlay && wantsPlayRef.current)) pause(); else void play(); };

  return {
    state,
    // Нажали «Послушать», видео ещё готовится.
    loading: pendingVideoPlay && state !== 'speaking',
    narration,
    activeSentence,
    // Доля сказанного 0…1 — для полосы прогресса.
    progress,
    toggle,
    pause,
    video: protectedVideo.url ? {
      ref: attachVideo,
      src: protectedVideo.url,
      // Прямая ссылка: браузер заранее подгружает начало ролика, по нажатию он стартует сразу.
      preload: canPrefetchVideo() ? 'auto' as const : 'metadata' as const,
      poster: posterUrl || undefined,
      muted: !audioEnabled,
      onPlay: () => setState('speaking'),
      onPause: () => setState((current) => (current === 'speaking' ? 'paused' : current)),
      onEnded: () => { setProgress(1); setState('completed'); },
      onError: () => {
        if (refreshedAfterErrorRef.current || !cueAssets.data) return;
        refreshedAfterErrorRef.current = true;
        // Подписанная ссылка истекла — берём свежую; новый src ролик подхватит сам.
        void cueAssets.refetch();
      },
      onTimeUpdate: (event: React.SyntheticEvent<HTMLVideoElement>) => {
        const element = event.currentTarget;
        if (Number.isFinite(element.duration) && element.duration > 0) setProgress(element.currentTime / element.duration);
      },
    } : null,
  };
}
