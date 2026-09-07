import api from './index'
import type { OrgMember, OrgWithRole, Project, ProjectWithRole } from '@/types'

export const orgsApi = {
  list: () => api.get<OrgWithRole[]>('/orgs/'),
  get: (orgId: string) => api.get<OrgWithRole>(`/orgs/${orgId}`),
  getBySlug: (slug: string) => api.get<OrgWithRole>(`/orgs/by-slug/${slug}`),
  create: (data: { name: string; slug?: string; icon?: string; description?: string }) =>
    api.post<OrgWithRole>('/orgs/', data),
  update: (orgId: string, data: Record<string, unknown>) => api.patch<OrgWithRole>(`/orgs/${orgId}`, data),
  remove: (orgId: string) => api.delete(`/orgs/${orgId}`),
  members: (orgId: string) => api.get<OrgMember[]>(`/orgs/${orgId}/members`),
  addMember: (orgId: string, data: { username: string; role: string }) =>
    api.post<OrgMember>(`/orgs/${orgId}/members`, data),
  updateMemberRole: (orgId: string, userId: number, role: string) =>
    api.patch<OrgMember>(`/orgs/${orgId}/members/${userId}`, { role }),
  removeMember: (orgId: string, userId: number) => api.delete(`/orgs/${orgId}/members/${userId}`),

  listProjects: (orgId: string) => api.get<ProjectWithRole[]>(`/orgs/${orgId}/projects/`),
  createProject: (orgId: string, data: { name: string; slug?: string; icon?: string; description?: string }) =>
    api.post<Project>(`/orgs/${orgId}/projects/`, data),
  projectBySlug: (orgId: string, slug: string) =>
    api.get<ProjectWithRole>(`/orgs/${orgId}/projects/by-slug/${slug}`),
}

export const projectsApi = {
  get: (projectId: string) => api.get<ProjectWithRole>(`/projects/${projectId}`),
  update: (projectId: string, data: Record<string, unknown>) =>
    api.patch<Project>(`/projects/${projectId}`, data),
  remove: (projectId: string) => api.delete(`/projects/${projectId}`),
  members: (projectId: string) => api.get(`/projects/${projectId}/members`),
  addMember: (projectId: string, data: { username: string; role?: string | null }) =>
    api.post(`/projects/${projectId}/members`, data),
  updateMemberRole: (projectId: string, userId: number, role: string | null) =>
    api.patch(`/projects/${projectId}/members/${userId}`, { role }),
  removeMember: (projectId: string, userId: number) => api.delete(`/projects/${projectId}/members/${userId}`),
}
