import { useMutation } from '@tanstack/react-query';

import { request, requestForm } from './client';
import type { KtpDraft, Subject } from './types';

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

export async function parseKtpFile(file: File): Promise<KtpDraft> {
  const formData = new FormData();
  formData.append('file', file);
  return requestForm<KtpDraft>('/ktp/parse', formData);
}
