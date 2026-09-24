import { ImagePlus, Loader2, Upload, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useCreateCustomPhotoAvatar, type AvatarProfile } from '@/lib/api';

type CustomAvatarUploaderProps = {
  teacherId: number;
  voiceId?: string;
  onCreated: (profile: AvatarProfile) => void | Promise<void>;
};

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png']);

export function customAvatarFileError(type: string, size: number): string {
  if (!ALLOWED_TYPES.has(type)) return 'Выберите PNG или JPEG.';
  if (size > MAX_FILE_BYTES) return 'Файл должен быть не больше 10 МБ.';
  return '';
}

export default function CustomAvatarUploader({ teacherId, voiceId, onCreated }: CustomAvatarUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [name, setName] = useState('');
  const [rightsConfirmed, setRightsConfirmed] = useState(false);
  const [validationError, setValidationError] = useState('');
  const [dimensions, setDimensions] = useState('');
  const createAvatar = useCreateCustomPhotoAvatar();

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const clearFile = () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setFile(null);
    setPreviewUrl('');
    setDimensions('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const chooseFile = (nextFile?: File) => {
    setValidationError('');
    if (!nextFile) return;
    const nextError = customAvatarFileError(nextFile.type, nextFile.size);
    if (nextError) return setValidationError(nextError);
    clearFile();
    const nextUrl = URL.createObjectURL(nextFile);
    setFile(nextFile);
    setPreviewUrl(nextUrl);
    if (!name.trim()) setName(nextFile.name.replace(/\.[^.]+$/, ''));
    const image = new Image();
    image.onload = () => setDimensions(`${image.naturalWidth} × ${image.naturalHeight}`);
    image.src = nextUrl;
  };

  const submit = async () => {
    if (!file || !name.trim() || !rightsConfirmed) return;
    const profile = await createAvatar.mutateAsync({
      name: name.trim(),
      teacherId,
      file,
      rightsConfirmed,
      voiceId: voiceId || undefined,
    });
    await onCreated(profile);
    clearFile();
    setName('');
    setRightsConfirmed(false);
    setOpen(false);
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex h-10 items-center gap-2 border border-border bg-background px-4 text-sm font-bold text-foreground hover:border-primary/50 hover:text-primary"
      >
        <ImagePlus className="h-4 w-4" /> Загрузить своего аватара
      </button>
    );
  }

  return (
    <div className="border border-dashed border-primary/40 bg-primary/[0.03] p-4">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="font-bold text-foreground">Свой фото-аватар</h3>
          <p className="mt-1 text-xs text-muted-foreground">Лучше всего работает фронтальный портрет одного человека при ровном освещении.</p>
        </div>
        <button type="button" onClick={() => setOpen(false)} title="Закрыть" className="grid h-8 w-8 place-items-center border border-border bg-background">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-[160px_minmax(0,1fr)]">
        <div className="relative aspect-square overflow-hidden border border-border bg-muted/30">
          {previewUrl ? (
            <img src={previewUrl} alt="Предпросмотр загруженного аватара" className="h-full w-full object-cover object-top" />
          ) : (
            <button type="button" onClick={() => inputRef.current?.click()} className="grid h-full w-full place-items-center text-center text-xs font-semibold text-muted-foreground">
              <span><Upload className="mx-auto mb-2 h-6 w-6 text-primary" />Выбрать портрет</span>
            </button>
          )}
          {previewUrl && (
            <button type="button" onClick={clearFile} title="Убрать фотографию" className="absolute right-2 top-2 grid h-8 w-8 place-items-center bg-background/90 shadow-sm">
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="space-y-3">
          <input ref={inputRef} type="file" accept="image/png,image/jpeg" className="hidden" onChange={(event) => chooseFile(event.target.files?.[0])} />
          <label className="block text-sm font-semibold text-foreground">
            Имя ведущего
            <input value={name} onChange={(event) => setName(event.target.value)} maxLength={255} placeholder="Например, Айжан эжей" className="mt-1.5 w-full border border-border bg-background px-3 py-2 font-normal" />
          </label>
          {file && (
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>{(file.size / 1024 / 1024).toFixed(1)} МБ</span>
              {dimensions && <span>{dimensions}</span>}
              <button type="button" onClick={() => inputRef.current?.click()} className="font-semibold text-primary">Заменить</button>
            </div>
          )}
          <label className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
            <input type="checkbox" checked={rightsConfirmed} onChange={(event) => setRightsConfirmed(event.target.checked)} className="mt-0.5 h-4 w-4 accent-primary" />
            <span>Я подтверждаю, что это моё изображение или у меня есть разрешение человека на создание и использование AI-аватара.</span>
          </label>
          {(validationError || createAvatar.error) && <p role="alert" className="text-xs font-semibold text-destructive">{validationError || (createAvatar.error as Error).message}</p>}
          <button
            type="button"
            onClick={() => void submit()}
            disabled={!file || !name.trim() || !rightsConfirmed || createAvatar.isPending}
            className="inline-flex h-10 items-center gap-2 bg-primary px-4 text-sm font-bold text-primary-foreground disabled:opacity-50"
          >
            {createAvatar.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
            {createAvatar.isPending ? 'Отправляем в HeyGen…' : 'Создать фото-аватара'}
          </button>
          <p className="text-xs text-muted-foreground">Обработка обычно занимает несколько минут. Вкладку можно закрыть: статус сохранится.</p>
        </div>
      </div>
    </div>
  );
}
