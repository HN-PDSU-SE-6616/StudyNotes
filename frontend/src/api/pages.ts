import api from './index'
import type { Block, PageDetail, PageStats, PageTreeNode } from '@/types'

export const pagesApi = {
  tree: () => api.get<PageTreeNode[]>('/pages/tree'),

  detail: (pageId: number) => api.get<PageDetail>(`/pages/${pageId}`),

  getBySlug: (slug: string) => api.get<PageDetail>(`/pages/by-slug/${slug}`),

  stats: (pageId: number) => api.get<PageStats>(`/pages/${pageId}/stats`),

  create: (data: { title: string; icon?: string; category?: string; parent_id?: number }) =>
    api.post('/pages/', data),

  update: (pageId: number, data: Record<string, unknown>) =>
    api.patch(`/pages/${pageId}`, data),

  remove: (pageId: number) => api.delete(`/pages/${pageId}`),

  duplicate: (pageId: number) => api.post(`/pages/${pageId}/duplicate`),

  syncLinkBlocks: (pageId: number) => api.post(`/pages/${pageId}/sync-link-blocks`),

  search: (q: string) => api.get('/pages/search', { params: { q } }),
}

export const blocksApi = {
  create: (pageId: number, data: { type: string; content?: Record<string, unknown>; sort_order?: number }) =>
    api.post<Block>(`/blocks/${pageId}`, data),

  update: (blockId: number, data: Record<string, unknown>) =>
    api.patch<Block>(`/blocks/${blockId}`, data),

  remove: (blockId: number) => api.delete(`/blocks/${blockId}`),

  reorder: (pageId: number, blockIds: number[]) =>
    api.put<Block[]>(`/blocks/${pageId}/reorder`, blockIds),

  duplicate: (blockId: number) => api.post<Block>(`/blocks/${blockId}/duplicate`),

  importToPage: (pageId: number, content: string, format: 'html' | 'md') =>
    api.post<Block[]>(`/blocks/${pageId}/import`, { content, format }),

  // 新：导入目录/文件到页面树
  importPages: (formData: FormData) =>
    api.post('/pages/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}
