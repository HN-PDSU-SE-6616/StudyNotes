import api from './index'
import type { FileMeta, RagResult, RecommendationItem } from '@/types'

export const filesApi = {
  /** 上传文档/附件（purpose: document | asset） */
  upload: (projectId: string, file: File, purpose: 'document' | 'asset') => {
    const form = new FormData()
    form.append('project_id', projectId)
    form.append('purpose', purpose)
    form.append('file', file)
    return api.post<FileMeta>('/files/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  list: (projectId: string) => api.get<FileMeta[]>(`/files/list/${projectId}`),
  contentUrl: (fileId: string) => `/api/v1/files/${fileId}/content`,
}

export const ragApi = {
  ask: (question: string, projectId?: string | null, topK = 8) =>
    api.post<RagResult>('/rag/ask', { question, project_id: projectId, top_k: topK }),
}

export const recommendationsApi = {
  list: () => api.get<RecommendationItem[]>('/recommendations/'),
}
