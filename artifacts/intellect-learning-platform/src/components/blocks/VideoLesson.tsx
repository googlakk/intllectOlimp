import { PlayCircle, AlertTriangle } from 'lucide-react';

export interface VideoLessonProps {
  title: string;
  drive_url: string;
  start_sec?: number;
  end_sec?: number;
  duration_min?: number;
  summary?: string[];
  questions?: Array<{ time_label?: string; question: string }>;
}

// Same rules as backend/curriculum.py drive_file_id.
export function driveFileId(url: string | undefined): string | null {
  if (!url) return null;
  const match =
    url.match(/drive\.google\.com\/file\/d\/([A-Za-z0-9_-]{10,})/) ??
    url.match(/drive\.google\.com\/(?:open|uc)\?(?:.*&)?id=([A-Za-z0-9_-]{10,})/);
  return match ? match[1] : null;
}

const clock = (sec: number) => `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, '0')}`;

export default function VideoLesson({ title, drive_url, start_sec, end_sec, duration_min, summary, questions }: VideoLessonProps) {
  const fileId = driveFileId(drive_url);
  // The Drive player cannot be seeked or paused from the page, so a fragment is shown as a hint.
  const fragment =
    typeof start_sec === 'number' || typeof end_sec === 'number'
      ? `Смотрите фрагмент ${clock(start_sec ?? 0)}${typeof end_sec === 'number' ? `–${clock(end_sec)}` : ''}`
      : null;

  return (
    <div className="my-6 space-y-4">
      <div className="flex items-center gap-3">
        <PlayCircle className="w-6 h-6 text-primary" />
        <h3 className="text-xl font-semibold text-foreground">{title}</h3>
        {duration_min ? <span className="text-sm text-muted-foreground font-medium">{duration_min} мин</span> : null}
      </div>

      {fileId ? (
        <div className="relative w-full overflow-hidden rounded-2xl border border-border bg-black" style={{ aspectRatio: '16 / 9' }}>
          <iframe
            src={`https://drive.google.com/file/d/${fileId}/preview`}
            title={title}
            className="absolute inset-0 w-full h-full"
            allow="autoplay; fullscreen"
            allowFullScreen
            loading="lazy"
          />
        </div>
      ) : (
        <div className="flex items-center gap-3 p-4 rounded-2xl border border-destructive/40 bg-destructive/5 text-sm text-destructive font-medium">
          <AlertTriangle className="w-5 h-5" /> Видео недоступно: неверная ссылка Google Drive
        </div>
      )}

      {fragment && <p className="text-sm font-semibold text-primary">{fragment}</p>}
      <p className="text-xs text-muted-foreground">
        Если видео не открывается, попросите учителя открыть доступ «Все, у кого есть ссылка».
      </p>

      {summary && summary.length > 0 && (
        <div className="rounded-2xl bg-muted/40 p-4">
          <div className="text-sm font-bold text-foreground mb-2">Главное из видео</div>
          <ul className="list-disc pl-5 space-y-1 text-sm text-foreground">
            {summary.map((point, i) => <li key={i}>{point}</li>)}
          </ul>
        </div>
      )}

      {questions && questions.length > 0 && (
        <div className="rounded-2xl border border-border p-4">
          <div className="text-sm font-bold text-foreground mb-2">Ответьте себе по ходу просмотра</div>
          <ol className="space-y-2 text-sm">
            {questions.map((q, i) => (
              <li key={i} className="flex gap-3">
                {q.time_label && <span className="font-mono font-bold text-primary shrink-0">{q.time_label}</span>}
                <span className="text-foreground">{q.question}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
