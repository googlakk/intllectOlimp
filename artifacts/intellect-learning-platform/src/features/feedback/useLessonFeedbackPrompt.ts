import { useCallback, useEffect, useRef, useState } from 'react';
import { feedbackAlreadyAsked, rememberFeedbackAsked } from './feedbackPrompt';

/** Даём ученику увидеть итог урока, потом спрашиваем. */
const ASK_DELAY_MS = 900;

export function useLessonFeedbackPrompt(topicId: number, versionId: number | null | undefined) {
  const [open, setOpen] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => () => { if (timer.current !== null) window.clearTimeout(timer.current); }, []);

  const ask = useCallback(() => {
    if (!topicId || feedbackAlreadyAsked(topicId, versionId)) return;
    rememberFeedbackAsked(topicId, versionId);
    timer.current = window.setTimeout(() => setOpen(true), ASK_DELAY_MS);
  }, [topicId, versionId]);

  const close = useCallback(() => setOpen(false), []);

  return { open, ask, close };
}
