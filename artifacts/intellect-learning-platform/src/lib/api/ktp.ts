import { useMutation } from '@tanstack/react-query';

import { request } from './client';
import type { Subject } from './types';

export const useUploadKtp = () =>
  useMutation({
    mutationFn: (data: unknown) =>
      request<{ status: string }>('/ktp/upload', { method: 'POST', body: JSON.stringify(data) }),
  });

export const uploadKtp = (data: unknown) =>
  request<Subject & { section_count: number; topic_count: number }>('/ktp/upload', {
    method: 'POST',
    body: JSON.stringify(data),
  });
