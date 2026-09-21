import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useUploadKtp } from '@/lib/api';
import { parseKtpJsonText } from './listModel';

export type KtpUploadState = {
  error: string | null;
  isUploading: boolean;
  success: string | null;
};

export const KTP_UPLOAD_SUCCESS_MESSAGE = 'КТП успешно загружен и обработан';

export function ktpUploadInvalidationKeys() {
  return [
    ['subjects'] as const,
    ['sections'] as const,
    ['topics'] as const,
  ];
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (event) => resolve(String(event.target?.result ?? ''));
    reader.onerror = () => reject(new Error('Ошибка чтения файла'));
    reader.readAsText(file);
  });
}

export function useKtpUploadWorkflow(onSettled?: () => void) {
  const queryClient = useQueryClient();
  const uploadMutation = useUploadKtp();
  const [state, setState] = useState<KtpUploadState>({
    error: null,
    isUploading: false,
    success: null,
  });

  const uploadFile = async (file: File | undefined) => {
    if (!file) return;

    setState({ error: null, isUploading: true, success: null });
    try {
      const text = await readFileAsText(file);
      const json = parseKtpJsonText(text);
      uploadMutation.mutate(json, {
        onSuccess: () => {
          ktpUploadInvalidationKeys().forEach((queryKey) => {
            queryClient.invalidateQueries({ queryKey });
          });
          setState({ error: null, isUploading: false, success: KTP_UPLOAD_SUCCESS_MESSAGE });
          onSettled?.();
        },
        onError: (error: Error) => {
          setState({ error: error.message || 'Ошибка загрузки КТП', isUploading: false, success: null });
          onSettled?.();
        },
      });
    } catch (error) {
      setState({
        error: error instanceof Error ? error.message : 'Файл должен быть валидным JSON',
        isUploading: false,
        success: null,
      });
      onSettled?.();
    }
  };

  return {
    ...state,
    uploadFile,
  };
}
