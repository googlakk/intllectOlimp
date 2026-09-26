import { useMutation, useQuery } from '@tanstack/react-query';
import { request, requestForm } from './client';
import type { AvatarCatalogItem, AvatarCueAsset, AvatarGenerationJob, AvatarProfile, GeneratedLesson } from './types';

export const getAvatarProfiles = () => request<AvatarProfile[]>('/avatar/profiles');
export const getAvatarCatalog = (query = '') => request<AvatarCatalogItem[]>(
  `/avatar/catalog/avatars${query ? `?q=${encodeURIComponent(query)}` : ''}`,
);
export const getVoiceCatalog = (language = 'ru') => (
  request<AvatarCatalogItem[]>(`/avatar/catalog/voices?language=${encodeURIComponent(language)}`)
);

export const createAvatarProfile = (data: {
  name: string;
  avatar_id: string;
  voice_id: string;
  supported_languages: string[];
  preview_image_url?: string;
  preview_audio_url?: string;
  consent_metadata?: Record<string, unknown>;
}) => request<AvatarProfile>('/avatar/profiles', { method: 'POST', body: JSON.stringify(data) });

export const createCustomPhotoAvatar = (data: {
  name: string;
  teacherId: number;
  file: File;
  rightsConfirmed: boolean;
  voiceId?: string;
}) => {
  const body = new FormData();
  body.set('name', data.name);
  body.set('teacher_id', String(data.teacherId));
  body.set('rights_confirmed', String(data.rightsConfirmed));
  if (data.voiceId) body.set('voice_id', data.voiceId);
  body.set('file', data.file);
  return requestForm<AvatarProfile>('/avatar/profiles/custom-photo', body);
};

export const updateAvatarProfileVoice = (profileId: number, voiceId: string) => (
  request<AvatarProfile>(`/avatar/profiles/${profileId}/voice`, {
    method: 'PUT',
    body: JSON.stringify({ voice_id: voiceId }),
  })
);

export const refreshCustomPhotoAvatar = (profileId: number) => (
  request<AvatarProfile>(`/avatar/profiles/${profileId}/refresh`, { method: 'POST' })
);

export const createAvatarJob = (data: {
  lesson_version_id: number;
  scene_id: string;
  beat_id?: string;
  cue_id?: string;
  profile_id: number;
  script: string;
  locale: string;
}) => request<AvatarGenerationJob>('/avatar/jobs', { method: 'POST', body: JSON.stringify(data) });

export const getAvatarJobs = (lessonVersionId: number) => (
  request<AvatarGenerationJob[]>(`/avatar/jobs?lesson_version_id=${lessonVersionId}`)
);
export const getAvatarCueAsset = (data: {
  lessonVersionId: number;
  cueId: string;
  sceneId?: string;
}) => {
  const params = new URLSearchParams({
    lesson_version_id: String(data.lessonVersionId),
    cue_id: data.cueId,
  });
  if (data.sceneId) params.set('scene_id', data.sceneId);
  return request<AvatarCueAsset | null>(`/avatar/cue-asset?${params.toString()}`);
};
export const getAvatarCueAssets = (lessonVersionId: number) => (
  request<AvatarCueAsset[]>(`/avatar/cue-assets?lesson_version_id=${lessonVersionId}`)
);
export const refreshAvatarJobs = (lessonVersionId: number) => (
  request<AvatarGenerationJob[]>(`/avatar/jobs/refresh?lesson_version_id=${lessonVersionId}`, { method: 'POST' })
);
export const selectLessonAvatarProfile = (lessonId: number, profileId: number) => (
  request<GeneratedLesson>(`/lessons/${lessonId}/avatar`, {
    method: 'PUT',
    body: JSON.stringify({ profile_id: profileId }),
  })
);

export const useAvatarProfiles = () => useQuery({
  queryKey: ['avatar-profiles'],
  queryFn: getAvatarProfiles,
});

export const useAvatarCatalog = (enabled: boolean, query = '') => useQuery({
  queryKey: ['avatar-catalog', query],
  queryFn: () => getAvatarCatalog(query),
  enabled,
  staleTime: 10 * 60 * 1000,
});

export const useVoiceCatalog = (enabled: boolean) => useQuery({
  queryKey: ['voice-catalog', 'ru'],
  queryFn: () => getVoiceCatalog('ru'),
  enabled,
  staleTime: 10 * 60 * 1000,
});

export const useCreateAvatarProfile = () => useMutation({ mutationFn: createAvatarProfile });
export const useCreateCustomPhotoAvatar = () => useMutation({ mutationFn: createCustomPhotoAvatar });
export const useUpdateAvatarProfileVoice = () => useMutation({
  mutationFn: ({ profileId, voiceId }: { profileId: number; voiceId: string }) => (
    updateAvatarProfileVoice(profileId, voiceId)
  ),
});
export const useRefreshCustomPhotoAvatar = () => useMutation({
  mutationFn: refreshCustomPhotoAvatar,
});
export const useCreateAvatarJob = () => useMutation({ mutationFn: createAvatarJob });
export const useAvatarJobs = (lessonVersionId?: number | null) => useQuery({
  queryKey: ['avatar-jobs', lessonVersionId],
  queryFn: () => getAvatarJobs(Number(lessonVersionId)),
  enabled: Boolean(lessonVersionId),
});
// Ссылки на видео всех реплик урока одним запросом. Сервер отдаёт ссылки, которым жить ещё 40+ минут;
// обновляем через 25 — ссылка не истекает, пока страница её держит.
const CUE_ASSETS_REFRESH_MS = 25 * 60 * 1000;
export const useAvatarCueAssets = (lessonVersionId?: number | null, enabled = true) => useQuery({
  queryKey: ['avatar-cue-assets', lessonVersionId],
  queryFn: () => getAvatarCueAssets(Number(lessonVersionId)),
  enabled: enabled && Boolean(lessonVersionId),
  staleTime: CUE_ASSETS_REFRESH_MS,
  refetchInterval: CUE_ASSETS_REFRESH_MS,
});
export const useRefreshAvatarJobs = () => useMutation({
  mutationFn: refreshAvatarJobs,
});
export const useSelectLessonAvatarProfile = () => useMutation({
  mutationFn: ({ lessonId, profileId }: { lessonId: number; profileId: number }) => (
    selectLessonAvatarProfile(lessonId, profileId)
  ),
});
