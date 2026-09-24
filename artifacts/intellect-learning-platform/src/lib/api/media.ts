import { request } from './client';
import type { BlockMediaPlan, EducationalImageRequest, EducationalImageResponse, EducationalVideoRequest, EducationalVideoResponse, LessonMediaPlan } from './types';

export const getLessonMediaPlan = (lessonId: number) =>
  request<LessonMediaPlan>('/media/lesson-plan', {
    method: 'POST',
    body: JSON.stringify({ lesson_id: lessonId }),
  });

export const getBlockMediaPlan = (payload: {
  lesson_id: number;
  block_index: number;
  slide_index?: number;
  preferred_kind?: 'image' | 'video';
}) => request<BlockMediaPlan>('/media/block-plan', {
  method: 'POST',
  body: JSON.stringify(payload),
});

export const generateEducationalImage = (payload: EducationalImageRequest) =>
  request<EducationalImageResponse>('/media/image', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const generateEducationalVideo = (payload: EducationalVideoRequest) =>
  request<EducationalVideoResponse>('/media/video', {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const getEducationalVideoStatus = (jobId: string) =>
  request<EducationalVideoResponse>(`/media/video/${encodeURIComponent(jobId)}`);
