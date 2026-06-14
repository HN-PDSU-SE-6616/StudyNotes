import api from './index'
import type { TokenResponse, User } from '@/types'

export const authApi = {
  login: (username: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { username, password }),

  register: (data: { username: string; email: string; password: string; display_name?: string }) =>
    api.post<TokenResponse>('/auth/register', data),

  me: () => api.get<User>('/auth/me'),

  updateMe: (data: { display_name?: string; avatar_url?: string }) =>
    api.patch<User>('/auth/me', data),
}
