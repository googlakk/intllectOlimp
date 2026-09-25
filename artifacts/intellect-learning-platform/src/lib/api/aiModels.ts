import { useQuery } from '@tanstack/react-query';

import { request } from './client';

export type AiModelOption = {
  id: string;
  provider: string;
  model: string;
  label: string;
  note: string;
  available: boolean;
  default: boolean;
};

export type AiModelGroup = {
  default: string;
  options: AiModelOption[];
};

export type AiModelCatalog = {
  lesson: AiModelGroup;
  image: AiModelGroup;
};

export const getAiModels = () => request<AiModelCatalog>('/ai/models');

export const useAiModels = () =>
  useQuery({
    queryKey: ['ai-models'],
    queryFn: getAiModels,
    staleTime: 10 * 60 * 1000,
  });
