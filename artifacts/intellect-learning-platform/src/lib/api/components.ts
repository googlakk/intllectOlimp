import { useQuery } from '@tanstack/react-query';

import { request } from './client';
import type { ComponentRegistryEntry } from './types';

export const useComponents = () =>
  useQuery({
    queryKey: ['components'],
    queryFn: () => request<ComponentRegistryEntry[]>('/components'),
  });
