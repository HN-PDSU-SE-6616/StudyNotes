import api from './index'
import type { Block, PageDetail, PageTreeNode } from '@/types'

export const pagesApi = {
  tree: () => api.get<PageTreeNode[]>('/pages/tree'),

  detail: (pageId: number) => api.get<PageDetail>(`/pages/${pageId}`),

  create: (data: { title: string; icon?: string; category?: string; parent_id?: number }) =>
    api.post('/pages/', data),

  update: (pageId: number, data: Record<string, unknown>) =>
    api.patch(`/pages/${pageId}`, data),

  remove: (pageId: number) => api.delete(`/pages/${pageId}`),

  search: (q: string) => api.get('/pages/search', { params: { q } }),
}

export const blocksApi = {
  create: (pageId: number, data: { type: string; content?: Record<string, unknown>; sort_order?: number }) =>
    api.post<Block>(`/blocks/${pageId}`, data),

  update: (blockId: number, data: Record<string, unknown>) =>
    api.patch<Block>(`/blocks/${blockId}`, data),

  remove: (blockId: number) => api.delete(`/blocks/${blockId}`),
}
