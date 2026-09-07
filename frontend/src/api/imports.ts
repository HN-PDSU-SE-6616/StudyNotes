import api from './index'

export interface ImportedNoteBrief {
  id: string
  title: string
  slug: string
  parent_id: string | null
  source_path: string | null
}

export interface ImportResponse {
  root_note_id?: string | null
  created: string[]
  reused: string[]
  skipped: string[]
  assets: number
  matched_target: boolean
  matched_doc?: string | null
  container_note_id?: string | null
  notes: ImportedNoteBrief[]
}

/**
 * 目录/多文件批量导入（multipart files；filename 保留 webkitRelativePath 目录结构）
 */
export const importsApi = {
  importNotes: (projectId: string, formData: FormData) =>
    api.post<ImportResponse>(`/projects/${projectId}/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 0, // 大目录导入可能较久
    }),
}
