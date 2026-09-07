import api from './index'

export interface UserProfile {
  user_id: number
  job_role: string | null
  job_role_custom: string | null
  tech_tags: string[]
  updated_at?: string | null
}

export interface ProfileSavePayload {
  job_role?: string | null
  job_role_custom?: string | null
  tech_tags?: string[] | null
}

export const profileApi = {
  options: () => api.get<{ options: { key: string; label: string; tags: string[] }[] }>(
    '/users/me/profile/options',
  ),
  get: () => api.get<UserProfile>('/users/me/profile'),
  save: (payload: ProfileSavePayload) => api.put<UserProfile>('/users/me/profile', payload),
}
