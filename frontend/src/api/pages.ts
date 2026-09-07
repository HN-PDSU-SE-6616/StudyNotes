import api from './index'
import type { Block, PageDetail, PageRead, PageStats, PageTreeNode } from '@/types'

/**
 * 笔记 API（后端 Note 语义）。树/列表/创建/搜索均需项目上下文。
 * 保留旧命名（pagesApi）以兼容现有编辑器组件。
 */
export const pagesApi = {
  // ---- 笔记 ----
  tree: (projectId: string) => api.get<PageTreeNode[]>(`/projects/${projectId}/notes/`),

  graph: (projectId: string) => api.get<{ nodes: unknown[]; edges: unknown[] }>(`/projects/${projectId}/notes/graph`),

  detail: (noteId: string) => api.get<PageDetail>(`/notes/${noteId}`),

  getBySlug: (projectId: string, slug: string) =>
    api.get<PageDetail>(`/projects/${projectId}/notes/by-slug/${slug}`),

  stats: (noteId: string) => api.get<PageStats>(`/notes/${noteId}/stats`),

  create: (projectId: string, data: { title: string; icon?: string; parent_id?: string | null }) =>
    api.post<PageRead>(`/projects/${projectId}/notes/`, data),

  update: (noteId: string, data: Record<string, unknown>) => api.patch<PageRead>(`/notes/${noteId}`, data),

  remove: (noteId: string) => api.delete(`/notes/${noteId}`),

  duplicate: (noteId: string) => api.post<PageRead>(`/notes/${noteId}/duplicate`),

  syncLinkBlocks: (noteId: string) => api.post(`/notes/${noteId}/sync-link-blocks`),

  search: (projectId: string, q: string) =>
    api.get<PageRead[]>(`/projects/${projectId}/notes/search`, { params: { q } }),

  // ---- ACL ----
  grantAcl: (noteId: string, data: { username: string; permission: string }) =>
    api.post(`/notes/${noteId}/acl`, data),
  revokeAcl: (noteId: string, userId: number) => api.delete(`/notes/${noteId}/acl/${userId}`),
}

export const blocksApi = {
  create: (noteId: string, data: { type: string; content?: Record<string, unknown>; sort_order?: number }) =>
    api.post<Block>(`/notes/${noteId}/blocks`, data),

  update: (blockId: string, data: Record<string, unknown>) =>
    api.patch<Block>(`/blocks/${blockId}`, data),

  remove: (blockId: string) => api.delete(`/blocks/${blockId}`),

  reorder: (noteId: string, blockIds: string[]) =>
    api.put<Block[]>(`/notes/${noteId}/blocks/reorder`, blockIds),

  duplicate: (blockId: string) => api.post<Block>(`/blocks/${blockId}/duplicate`),

  importToNote: (noteId: string, content: string, format: 'html' | 'md') =>
    api.post<Block[]>(`/notes/${noteId}/blocks/import`, { content, format }),
}
