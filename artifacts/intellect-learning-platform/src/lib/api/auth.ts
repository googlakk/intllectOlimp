import { request } from './client';
import type { AuthSession } from '../authSession';
import type { User } from './types';

export const loginWithPassword = (login: string, password: string) =>
  request<AuthSession>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ login, password }),
  });

export const getCurrentUser = () => request<User>('/auth/me');

export const changePassword = (newPassword: string) =>
  request<{ ok: boolean }>('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword }),
  });

export const logoutSession = () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' });
