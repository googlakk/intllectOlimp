import {
  Check, CircleAlert, Clock3, Loader2, Play, RefreshCw, Search, UserRound, Volume2,
} from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  useAvatarCatalog,
  useAvatarJobs,
  useAvatarProfiles,
  useCreateAvatarJob,
  useCreateAvatarProfile,
  useRefreshAvatarJobs,
  useRefreshCustomPhotoAvatar,
  useSelectLessonAvatarProfile,
  useUpdateAvatarProfileVoice,
  useVoiceCatalog,
  type AvatarCatalogItem,
  type AvatarCue,
  type AvatarProfile,
  type GeneratedLesson,
} from '@/lib/api';
import { AvatarCompanion } from '@/features/lessons/AvatarCompanion';
import { useAuth } from '@/components/auth/AuthContext';
import CustomAvatarUploader from './CustomAvatarUploader';

type AvatarConfigurationPanelProps = { lesson: GeneratedLesson };

function itemId(item: AvatarCatalogItem, kind: 'avatar' | 'voice'): string {
  const value = kind === 'avatar' ? item.avatar_id || item.id : item.voice_id || item.id;
  return typeof value === 'string' ? value : '';
}

function itemName(item: AvatarCatalogItem, fallback: string): string {
  const value = item.display_name || item.avatar_name || item.name;
  return typeof value === 'string' ? value : fallback;
}

function itemUrl(item: AvatarCatalogItem, kind: 'image' | 'audio' | 'video'): string | undefined {
  const candidates = kind === 'image'
    ? [item.preview_image_url, item.preview_url]
    : kind === 'video'
      ? [item.preview_video_url]
      : [item.preview_audio_url, item.preview_audio, item.audio_url];
  return candidates.find((value): value is string => typeof value === 'string' && value.length > 0);
}

function jobCueId(job: { request_payload?: Record<string, unknown> }): string {
  return typeof job.request_payload?.cue_id === 'string' ? job.request_payload.cue_id : '';
}

function profileProcessingStatus(profile?: { consent_metadata?: Record<string, unknown> }): string {
  return typeof profile?.consent_metadata?.status === 'string'
    ? profile.consent_metadata.status.toLocaleLowerCase('en')
    : 'completed';
}

function isProfileProcessing(status: string): boolean {
  return ['pending', 'queued', 'waiting', 'processing'].includes(status);
}

export default function AvatarConfigurationPanel({ lesson }: AvatarConfigurationPanelProps) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [avatarId, setAvatarId] = useState('');
  const [voiceId, setVoiceId] = useState('');
  const [profileId, setProfileId] = useState<number | ''>(
    lesson.lesson_document?.avatar.profile_id || '',
  );
  const [search, setSearch] = useState('');
  const [catalogSearch, setCatalogSearch] = useState('');
  const [catalogEnabled, setCatalogEnabled] = useState(false);
  const [status, setStatus] = useState('');
  const [actionError, setActionError] = useState('');
  const [previewAudio, setPreviewAudio] = useState(true);
  const refreshingRef = useRef(false);
  const profiles = useAvatarProfiles();
  const avatars = useAvatarCatalog(catalogEnabled, catalogSearch);
  const voices = useVoiceCatalog(true);
  const jobs = useAvatarJobs(lesson.active_version_id);
  const createProfile = useCreateAvatarProfile();
  const updateProfileVoice = useUpdateAvatarProfileVoice();
  const refreshCustomProfile = useRefreshCustomPhotoAvatar();
  const createJob = useCreateAvatarJob();
  const refreshJobs = useRefreshAvatarJobs();
  const selectProfile = useSelectLessonAvatarProfile();

  const selectedProfile = profiles.data?.find((profile) => profile.id === Number(profileId));
  const selectedAvatar = avatars.data?.find((item) => itemId(item, 'avatar') === avatarId);
  const selectedVoice = voices.data?.find((item) => itemId(item, 'voice') === voiceId);
  const filteredAvatars = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('ru');
    const source = avatars.data || [];
    if (!needle) return source;
    return source.filter((item, index) => (
      itemName(item, `Аватар ${index + 1}`).toLocaleLowerCase('ru').includes(needle)
      || String(item.type || '').toLocaleLowerCase('ru').includes(needle)
    ));
  }, [avatars.data, search]);
  const cues = useMemo(() => (
    lesson.lesson_document?.episodes.flatMap((episode) => (
      episode.scenes.flatMap((scene) => scene.avatar_cues.map((cue) => ({ scene, cue })))
    )) || []
  ), [lesson.lesson_document]);
  const pendingJobs = jobs.data?.filter((job) => !['completed', 'failed', 'cancelled'].includes(job.status)) || [];
  const completedJobs = jobs.data?.filter((job) => job.status === 'completed').length || 0;
  const selectedProfileStatus = profileProcessingStatus(selectedProfile);
  const selectedProfileReady = selectedProfileStatus === 'completed';

  useEffect(() => {
    const timer = window.setTimeout(() => setCatalogSearch(search.trim()), 350);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!selectedProfile) return;
    setAvatarId(selectedProfile.provider_avatar_id);
    setVoiceId(selectedProfile.provider_voice_id || '');
  }, [selectedProfile]);

  useEffect(() => {
    if (!lesson.active_version_id || pendingJobs.length === 0) return undefined;
    const refresh = async () => {
      if (refreshingRef.current || !lesson.active_version_id) return;
      refreshingRef.current = true;
      try {
        const updated = await refreshJobs.mutateAsync(lesson.active_version_id);
        queryClient.setQueryData(['avatar-jobs', lesson.active_version_id], updated);
        if (updated.some((job) => job.status === 'completed')) {
          await queryClient.invalidateQueries({ queryKey: ['lesson', lesson.topic_id] });
        }
      } finally {
        refreshingRef.current = false;
      }
    };
    const first = window.setTimeout(() => void refresh(), 600);
    const timer = window.setInterval(() => void refresh(), 8000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(timer);
    };
  }, [lesson.active_version_id, lesson.topic_id, pendingJobs.length, queryClient]);

  useEffect(() => {
    const processing = profiles.data?.filter((profile) => (
      profile.consent_metadata?.source === 'teacher_photo_upload'
      && isProfileProcessing(profileProcessingStatus(profile))
    )) || [];
    if (processing.length === 0) return undefined;
    const refresh = async () => {
      await Promise.all(processing.map((profile) => refreshCustomProfile.mutateAsync(profile.id)));
      await queryClient.invalidateQueries({ queryKey: ['avatar-profiles'] });
    };
    const timer = window.setInterval(() => void refresh(), 8000);
    return () => window.clearInterval(timer);
  }, [profiles.data, queryClient]);

  const chooseProfile = async (nextId: number) => {
    setActionError('');
    setProfileId(nextId);
    const profile = profiles.data?.find((item) => item.id === nextId);
    if (profile) {
      setAvatarId(profile.provider_avatar_id);
      setVoiceId(profile.provider_voice_id || '');
      if (isProfileProcessing(profileProcessingStatus(profile))) {
        setStatus('Аватар ещё обрабатывается. Назначить его уроку можно после завершения.');
        return;
      }
      if (profileProcessingStatus(profile) === 'failed') {
        setStatus('Этот аватар не был создан. Загрузите другое фото.');
        return;
      }
    }
    try {
      await selectProfile.mutateAsync({ lessonId: lesson.id, profileId: nextId });
      await queryClient.invalidateQueries({ queryKey: ['lesson', lesson.topic_id] });
      setStatus('Профиль выбран для этого урока. Ученик увидит его в помощнике.');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Не удалось выбрать профиль аватара');
    }
  };

  const saveProfile = async () => {
    setActionError('');
    if (!avatarId) {
      setActionError('Сначала выберите аватара.');
      return;
    }
    if (!voiceId) {
      setActionError('Для аватара нужно выбрать голос.');
      return;
    }
    try {
      if (selectedProfile?.provider_avatar_id === avatarId) {
        if (!selectedProfileReady) return;
        if (selectedProfile.provider_voice_id !== voiceId) {
          await updateProfileVoice.mutateAsync({ profileId: selectedProfile.id, voiceId });
          await queryClient.invalidateQueries({ queryKey: ['avatar-profiles'] });
        }
        await chooseProfile(selectedProfile.id);
        return;
      }
      const profile = await createProfile.mutateAsync({
        name: `Ведущий ${itemName(selectedAvatar || {}, avatarId)}`,
        avatar_id: avatarId,
        voice_id: voiceId,
        supported_languages: ['ru', 'ky'],
        preview_image_url: selectedAvatar ? itemUrl(selectedAvatar, 'image') : undefined,
        preview_audio_url: selectedVoice ? itemUrl(selectedVoice, 'audio') : undefined,
        consent_metadata: {
          preview_video_url: selectedAvatar ? itemUrl(selectedAvatar, 'video') : undefined,
        },
      });
      await queryClient.invalidateQueries({ queryKey: ['avatar-profiles'] });
      await chooseProfile(profile.id);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Не удалось сохранить аватара');
    }
  };

  const customAvatarCreated = async (profile: AvatarProfile) => {
    setActionError('');
    setProfileId(profile.id);
    setAvatarId(profile.provider_avatar_id);
    setVoiceId(profile.provider_voice_id || voiceId);
    await queryClient.invalidateQueries({ queryKey: ['avatar-profiles'] });
    setStatus('Фото принято. После обработки выберите голос и нажмите «Сохранить и выбрать».');
  };

  const generate = async () => {
    setActionError('');
    if (!lesson.active_version_id || !profileId) return;
    if (!selectedProfileReady) {
      setActionError('Аватар ещё обрабатывается. Подождите завершения HeyGen.');
      return;
    }
    if (!voiceId) {
      setActionError('Для аватара не выбран голос. Выберите русский голос и нажмите «Сохранить и выбрать».');
      return;
    }
    try {
      setStatus(`Отправка реплик: 0 из ${cues.length}`);
      for (let index = 0; index < cues.length; index += 1) {
        const { scene, cue } = cues[index];
        await createJob.mutateAsync({
          lesson_version_id: lesson.active_version_id,
          scene_id: scene.id,
          beat_id: cue.beat_id,
          cue_id: cue.id,
          profile_id: Number(profileId),
          script: cue.script,
          locale: 'ru-RU',
        });
        setStatus(`Отправка реплик: ${index + 1} из ${cues.length}`);
      }
      await jobs.refetch();
      setStatus('HeyGen создаёт реплики. Готовые видео автоматически появятся на своих слайдах.');
    } catch (error) {
      setStatus('');
      setActionError(error instanceof Error ? error.message : 'Не удалось создать реплики аватара');
    }
  };

  const profilePreviewVideo = selectedProfile?.consent_metadata?.preview_video_url;
  const previewVideo = itemUrl(selectedAvatar || {}, 'video')
    || (typeof profilePreviewVideo === 'string' ? profilePreviewVideo : undefined);
  const previewImage = itemUrl(selectedAvatar || {}, 'image') || selectedProfile?.preview_image_url;
  const previewCue: AvatarCue | undefined = cues[0]?.cue ? {
    ...cues[0].cue,
    video_url: previewVideo,
    poster_url: previewImage || undefined,
  } : undefined;
  const error = profiles.error || avatars.error || voices.error || jobs.error
    || createProfile.error || createJob.error || refreshJobs.error || selectProfile.error
    || updateProfileVoice.error || refreshCustomProfile.error;

  return (
    <section className="mb-8 border-y border-border py-6" aria-labelledby="avatar-settings-title">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="avatar-settings-title" className="flex items-center gap-2 text-lg font-bold text-foreground">
            <UserRound className="h-5 w-5 text-primary" /> Аватар и голос
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Выберите ведущего визуально, прослушайте голос и проверьте помощника до публикации.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            if (!catalogEnabled) {
              setCatalogEnabled(true);
              return;
            }
            void Promise.all([avatars.refetch(), voices.refetch(), jobs.refetch()]);
          }}
          disabled={avatars.isFetching || voices.isFetching || jobs.isFetching}
          title="Обновить каталоги и статусы"
          className="grid h-10 w-10 place-items-center rounded-md border border-border hover:bg-muted disabled:opacity-50"
        >
          {(avatars.isFetching || voices.isFetching || jobs.isFetching)
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <RefreshCw className="h-4 w-4" />}
        </button>
      </div>

      {(actionError || error) && <p role="alert" className="mb-4 flex items-center gap-2 text-sm font-semibold text-destructive"><CircleAlert className="h-4 w-4" />{actionError || (error as Error).message}</p>}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-6">
          {profiles.data && profiles.data.length > 0 && (
            <div>
              <h3 className="mb-3 text-sm font-bold text-foreground">Сохранённые ведущие</h3>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {profiles.data.map((profile) => (
                  <button
                    key={profile.id}
                    type="button"
                    onClick={() => void chooseProfile(profile.id)}
                    className={`relative overflow-hidden rounded-lg border text-left transition-colors ${profileId === profile.id ? 'border-primary ring-2 ring-primary/20' : 'border-border hover:border-primary/50'}`}
                  >
                    <div className="aspect-video bg-muted">
                      {profile.preview_image_url
                        ? <img src={profile.preview_image_url} alt="" className="h-full w-full object-cover object-top" />
                        : <UserRound className="m-auto h-full w-10 text-muted-foreground" />}
                    </div>
                    <span className="block truncate px-3 py-2 text-sm font-semibold">{profile.name}</span>
                    {isProfileProcessing(profileProcessingStatus(profile)) && (
                      <span className="absolute left-2 top-2 inline-flex items-center gap-1 bg-background/90 px-2 py-1 text-[10px] font-bold text-muted-foreground">
                        <Clock3 className="h-3 w-3" /> Обработка
                      </span>
                    )}
                    {profileProcessingStatus(profile) === 'failed' && (
                      <span className="absolute left-2 top-2 bg-destructive px-2 py-1 text-[10px] font-bold text-destructive-foreground">Ошибка</span>
                    )}
                    {profileId === profile.id && <Check className="absolute right-2 top-2 h-5 w-5 rounded-full bg-primary p-1 text-primary-foreground" />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {user?.id && (
            <CustomAvatarUploader
              teacherId={user.id}
              voiceId={voiceId || undefined}
              onCreated={customAvatarCreated}
            />
          )}

          <div>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-bold text-foreground">Каталог HeyGen</h3>
              <label className="relative w-full sm:w-64">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Найти аватара" className="w-full rounded-md border border-border bg-background py-2 pl-9 pr-3 text-sm" />
              </label>
            </div>
            {!catalogEnabled ? (
              <button type="button" onClick={() => setCatalogEnabled(true)} className="flex h-32 w-full flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-muted/20 text-sm font-semibold hover:border-primary/50 hover:bg-muted/40">
                <UserRound className="h-6 w-6 text-primary" />
                Открыть визуальный каталог
                <span className="text-xs font-normal text-muted-foreground">Портреты и видео загружаются напрямую из HeyGen</span>
              </button>
            ) : avatars.isLoading ? (
              <div className="grid h-40 place-items-center"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
            ) : (
              <div className="grid max-h-[420px] grid-cols-2 gap-3 overflow-y-auto pr-2 sm:grid-cols-3 lg:grid-cols-4">
                {filteredAvatars.map((item, index) => {
                  const id = itemId(item, 'avatar');
                  return (
                    <button key={id || index} type="button" onClick={() => setAvatarId(id)} className={`relative overflow-hidden rounded-lg border text-left ${avatarId === id ? 'border-primary ring-2 ring-primary/20' : 'border-border hover:border-primary/50'}`}>
                      <div className="aspect-square bg-muted">
                        {itemUrl(item, 'image')
                          ? <img src={itemUrl(item, 'image')} alt="" loading="lazy" className="h-full w-full object-cover object-top" />
                          : <UserRound className="m-auto h-full w-10 text-muted-foreground" />}
                      </div>
                      <span className="block truncate px-2 py-2 text-xs font-semibold">{itemName(item, `Аватар ${index + 1}`)}</span>
                      {avatarId === id && <Check className="absolute right-2 top-2 h-5 w-5 rounded-full bg-primary p-1 text-primary-foreground" />}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div>
            <h3 className="mb-3 text-sm font-bold text-foreground">Русский голос</h3>
            {voices.isLoading ? (
              <div className="grid h-24 place-items-center rounded-lg border border-border bg-muted/20">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
              </div>
            ) : voices.data && voices.data.length > 0 ? (
              <div className="grid max-h-56 gap-2 overflow-y-auto pr-2 sm:grid-cols-2">
                {voices.data.map((item, index) => {
                const id = itemId(item, 'voice');
                const audio = itemUrl(item, 'audio');
                return (
                  <div key={id || index} className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${voiceId === id ? 'border-primary bg-primary/5' : 'border-border'}`}>
                    <button type="button" onClick={() => setVoiceId(id)} className="min-w-0 flex-1 text-left">
                      <span className="block truncate text-sm font-semibold">{itemName(item, `Голос ${index + 1}`)}</span>
                      <span className="block text-xs text-muted-foreground">{String(item.language || item.locale || item.gender || 'HeyGen')}</span>
                    </button>
                    {audio && <audio controls src={audio} className="h-8 w-28" />}
                  </div>
                );
                })}
              </div>
            ) : (
              <p className="rounded-lg border border-border bg-muted/20 px-3 py-4 text-sm text-muted-foreground">
                Голоса HeyGen не найдены. Нажмите кнопку обновления сверху или проверьте HEYGEN_API_KEY.
              </p>
            )}
          </div>
        </div>

        <div className="space-y-3 xl:sticky xl:top-0 xl:self-start">
          <h3 className="text-sm font-bold text-foreground">Предпросмотр в уроке</h3>
          {previewCue ? (
            <AvatarCompanion
              cue={previewCue}
              previewImageUrl={previewImage}
              companionName={selectedProfile?.name || itemName(selectedAvatar || {}, 'Помощник')}
              avatarEnabled
              audioEnabled={previewAudio}
              onAvatarEnabledChange={() => undefined}
              onAudioEnabledChange={setPreviewAudio}
            />
          ) : (
            <div className="grid aspect-video place-items-center rounded-lg border border-border bg-muted/20 text-sm text-muted-foreground">В уроке пока нет реплик</div>
          )}
          <p className="text-xs leading-relaxed text-muted-foreground">Видео здесь показывает внешний вид ведущего. В уроке каждая реплика будет синхронизирована со своим слайдом или блоком.</p>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-5">
        <button type="button" onClick={() => void saveProfile()} disabled={!avatarId || !voiceId || (selectedProfile ? !selectedProfileReady : false) || createProfile.isPending || selectProfile.isPending} className="rounded-lg border border-border px-4 py-2 text-sm font-bold hover:bg-muted disabled:opacity-50">
          Сохранить и выбрать
        </button>
        <button type="button" onClick={() => void generate()} disabled={!profileId || !selectedProfileReady || !voiceId || !lesson.active_version_id || cues.length === 0 || createJob.isPending} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground disabled:opacity-50">
          {createJob.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          Создать {cues.length} реплик
        </button>
        {jobs.data && jobs.data.length > 0 && (
          <span className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground">
            {pendingJobs.length > 0 ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : <Check className="h-4 w-4 text-green-600" />}
            Готово {completedJobs} из {jobs.data.length}
          </span>
        )}
        {selectedVoice && itemUrl(selectedVoice, 'audio') && <Volume2 className="h-4 w-4 text-primary" />}
      </div>
      {selectedProfile && isProfileProcessing(selectedProfileStatus) && (
        <p className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin text-primary" />Аватар ещё обрабатывается. Генерация реплик станет доступна автоматически.</p>
      )}
      {selectedProfile && selectedProfileReady && !voiceId && (
        <p className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-amber-700"><CircleAlert className="h-4 w-4" />Выберите русский голос и нажмите «Сохранить и выбрать», затем можно создавать реплики.</p>
      )}
      {selectedProfile && selectedProfileStatus === 'failed' && (
        <p className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-destructive"><CircleAlert className="h-4 w-4" />HeyGen не смог создать аватара. Загрузите другое фото с одним человеком анфас.</p>
      )}
      {status && <p className="mt-3 text-sm font-medium text-muted-foreground" aria-live="polite">{status}</p>}
      {jobs.data?.some((job) => job.status === 'failed') && (
        <div className="mt-3 text-sm text-destructive">Не удалось создать: {jobs.data.filter((job) => job.status === 'failed').map((job) => jobCueId(job) || `задача ${job.id}`).join(', ')}</div>
      )}
    </section>
  );
}
