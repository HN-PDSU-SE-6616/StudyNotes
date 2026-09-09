import api from './index'
import type { FileMeta, RagResult, RecommendationItem } from '@/types'

export const filesApi = {
  /** 上传文档/附件（purpose: document | asset；category 见后端 FileCategory） */
  upload: (projectId: string, file: File, purpose: 'document' | 'asset', category?: string) => {
    const form = new FormData()
    form.append('project_id', projectId)
    form.append('purpose', purpose)
    if (category) form.append('category', category)
    form.append('file', file)
    return api.post<FileMeta>('/files/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  /** 上传用户级媒体（头像/AI 小助手图标背景等，无需 project_id） */
  uploadMine: (file: File, category: 'user_avatar' | 'assistant_icon' | 'assistant_bg' | 'assistant_media') => {
    const form = new FormData()
    form.append('category', category)
    form.append('file', file)
    return api.post<FileMeta>('/files/mine', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  listMine: () => api.get<FileMeta[]>('/files/mine'),
  deleteMine: (fileId: string) => api.delete<{ message: string }>(`/files/mine/${fileId}`),
  list: (projectId: string) => api.get<FileMeta[]>(`/files/list/${projectId}`),
  contentUrl: (fileId: string, mine = false) =>
    mine ? `/api/v1/files/mine/${fileId}/content` : `/api/v1/files/${fileId}/content`,
}

export const ragApi = {
  ask: (question: string, projectId?: string | null, topK = 8) =>
    api.post<RagResult>('/rag/ask', { question, project_id: projectId, top_k: topK }),
}

export const recommendationsApi = {
  list: () => api.get<RecommendationItem[]>('/recommendations/'),
}
