import { useEffect, useMemo, useRef, useState } from 'react';
import { getAvatarCueAsset } from '@/lib/api/avatar';
import type { AvatarCue } from '@/lib/api/types';
import { useProtectedMediaUrl } from '@/lib/useProtectedMediaUrl';
import { activeNarrationSentence, narrationSegments, narrationSpeechText } from './avatarNarration';

/** Видео заранее не качаем, если ученик экономит трафик или сеть медленная: скачаем по нажатию. */
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
 * Видео реплики ищется и скачивается заранее, при смене шага: по нажатию оно стартует сразу.
 * Пока видео грузится, голос браузера не включается — иначе звучат два рассказчика подряд.
 */
export function useAvatarNarration({ cue, lessonVersionId, avatarEnabled, audioEnabled, onAudioEnabledChange }: Options) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const playbackTokenRef = useRef(0);
  const speechSegmentRef = useRef(0);
  const [state, setState] = useState<NarratorState>('ready');
  const [progress, setProgress] = useState(0);
  const [videoRequested, setVideoRequested] = useState(false);
  const [pendingVideoPlay, setPendingVideoPlay] = useState(false);
  const [lazyVideoUrl, setLazyVideoUrl] = useState<string | undefined>(cue?.video_url);
  const [lazyPosterUrl, setLazyPosterUrl] = useState<string | undefined | null>(cue?.poster_url);
  const [assetLookupDone, setAssetLookupDone] = useState(Boolean(cue?.video_url));
  // Нажали «Послушать», пока видео ещё ищется или скачивается: запустим его, как только будет готово.
  const wantsPlayRef = useRef(false);
  const lookupRunningRef = useRef(false);
  const narration = narrationSpeechText(cue?.fallback_text || cue?.script || '');
  const effectiveVideoUrl = lazyVideoUrl || cue?.video_url;
  const protectedVideo = useProtectedMediaUrl(effectiveVideoUrl, { enabled: videoRequested && Boolean(effectiveVideoUrl) });
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
    lookupRunningRef.current = false;
    setLazyVideoUrl(cue?.video_url);
    setLazyPosterUrl(cue?.poster_url);
    setAssetLookupDone(Boolean(cue?.video_url));
    // Готовое видео скачиваем сразу, не дожидаясь нажатия.
    if (avatarEnabled && cue?.video_url && canPrefetchVideo()) setVideoRequested(true);
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.currentTime = 0;
      videoRef.current.load();
    }
  }, [cue?.id, cue?.beat_id, cue?.video_url, cue?.poster_url]); // eslint-disable-line react-hooks/exhaustive-deps

  // Видео реплики ищем заранее: к нажатию «Послушать» оно уже скачано.
  useEffect(() => {
    if (!avatarEnabled || assetLookupDone || !lessonVersionId || !cue?.id) return undefined;
    let cancelled = false;
    setAssetLookupDone(true);
    lookupRunningRef.current = true;
    getAvatarCueAsset({ lessonVersionId, cueId: cue.id, sceneId: cue.scene_id })
      .then((asset) => {
        // Ответ для прошлой реплики не трогает флаг текущего поиска.
        if (cancelled) return;
        lookupRunningRef.current = false;
        if (asset?.video_url) {
          setLazyVideoUrl(asset.video_url);
          setLazyPosterUrl(asset.poster_url);
          if (canPrefetchVideo() || wantsPlayRef.current) setVideoRequested(true);
        } else if (wantsPlayRef.current) {
          wantsPlayRef.current = false;
          setPendingVideoPlay(false);
          speakFallback();
        }
      })
      .catch(() => {
        if (cancelled) return;
        lookupRunningRef.current = false;
        if (wantsPlayRef.current) { wantsPlayRef.current = false; setPendingVideoPlay(false); speakFallback(); }
      });
    return () => { cancelled = true; };
  }, [avatarEnabled, assetLookupDone, lessonVersionId, cue?.id, cue?.scene_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Видео не скачалось — объяснит голос браузера, если ученик уже ждёт.
  useEffect(() => {
    if (!protectedVideo.error || !wantsPlayRef.current) return;
    wantsPlayRef.current = false;
    setPendingVideoPlay(false);
    speakFallback();
  }, [protectedVideo.error]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!pendingVideoPlay || !protectedVideo.url || !videoRef.current) return;
    wantsPlayRef.current = false;
    window.speechSynthesis?.cancel();
    videoRef.current.muted = false;
    void videoRef.current.play()
      .then(() => { setPendingVideoPlay(false); setState('speaking'); })
      .catch(() => { setPendingVideoPlay(false); setState('paused'); });
  }, [pendingVideoPlay, protectedVideo.url]);

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
    const lookupPending = !effectiveVideoUrl && !assetLookupDone && Boolean(lessonVersionId && cue?.id) && avatarEnabled;
    const lookupInFlight = !effectiveVideoUrl && assetLookupDone && avatarEnabled && lookupRunningRef.current;
    if (lookupPending || lookupInFlight || (effectiveVideoUrl && !protectedVideo.url && !protectedVideo.error)) {
      // Видео ещё ищется или скачивается — ждём его, без голоса браузера.
      wantsPlayRef.current = true;
      if (effectiveVideoUrl) setVideoRequested(true);
      setPendingVideoPlay(true);
      setState('paused');
      return;
    }
    if (!protectedVideo.url || !videoRef.current) {
      speakFallback();
      return;
    }
    if (state === 'completed') {
      videoRef.current.currentTime = 0;
      setProgress(0);
    }
    videoRef.current.muted = false;
    try {
      await videoRef.current.play();
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
    toggle,
    pause,
    video: protectedVideo.url ? {
      ref: videoRef,
      src: protectedVideo.url,
      poster: lazyPosterUrl || cue?.poster_url || undefined,
      muted: !audioEnabled,
      onPlay: () => setState('speaking'),
      onPause: () => setState((current) => (current === 'speaking' ? 'paused' : current)),
      onEnded: () => { setProgress(1); setState('completed'); },
      onTimeUpdate: (event: React.SyntheticEvent<HTMLVideoElement>) => {
        const element = event.currentTarget;
        if (Number.isFinite(element.duration) && element.duration > 0) setProgress(element.currentTime / element.duration);
      },
    } : null,
  };
}
