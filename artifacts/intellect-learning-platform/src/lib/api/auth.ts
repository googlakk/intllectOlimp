import { useMutation, useQuery } from '@tanstack/react-query';

import { request } from './client';
import type { LoginUsers, User } from './types';

export const useLoginUsers = () =>
  useQuery({ queryKey: ['login-users'], queryFn: () => request<LoginUsers>('/auth/users') });

export const useLogin = () =>
  useMutation({
    mutationFn: (data: { role: 'student' | 'teacher'; name: string }) =>
      request<User>('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  });
