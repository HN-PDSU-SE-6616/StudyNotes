/** 用户 */
export interface User {
  id: number
  username: string
  email: string
  display_name: string
  avatar_url: string | null
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

// ============ 组织 / 项目 ============

export interface Org {
  id: string
  name: string
  slug: string
  icon: string | null
  description: string | null
  owner_id: number
  created_at: string
}

export interface OrgWithRole extends Org {
  my_role: string
}

export interface Project {
  id: string
  organization_id: string
  name: string
  slug: string
  icon: string | null
  description: string | null
  is_archived: boolean
  creator_id: number
  created_at: string
  updated_at: string
}

export interface ProjectWithRole extends Project {
  my_role: string
}

export interface OrgMember {
  user_id: number
  username: string
  display_name: string
  avatar_url: string | null
  role: string
  created_at: string
}

// ============ 笔记（兼容旧 Page 命名，字段与后端 Note 对齐） ============

/** 笔记基础信息 */
export interface PageRead {
  id: string
  project_id: string
  slug: string
  title: string
  icon: string | null
  category?: string
  parent_id: string | null
  sort_order: number
  is_pinned: boolean
  is_public: boolean
  owner_id: number
  creator_id: number | null
  last_editor_id: number | null
  view_count: number
  created_at: string
  updated_at: string
}

/** 笔记树节点 */
export interface PageTreeNode extends PageRead {
  children: PageTreeNode[]
  linked_children: PageTreeNode[]
}

/** 内容块 */
export interface Block {
  id: string
  note_id: string
  type: string
  content: Record<string, unknown>
  sort_order: number
  created_at: string
  updated_at: string
}

/** 笔记详情 */
export interface PageDetail extends PageRead {
  blocks: Block[]
}

export interface PageStats {
  total_words: number
  block_count: number
  view_count: number
  created_at: string
  creator_name: string | null
  updated_at: string
  last_editor_name: string | null
}

// ============ AI / 推荐 ============

export interface RagSource {
  note_id: string
  title: string
  slug: string
  project_id: string
  heading_path: string
  page: number | null
  anchor: string
  score: number
  excerpt: string
}

export interface RagResult {
  answer: string
  sources: RagSource[]
}

export interface RecommendationItem {
  note_id: string
  title: string
  slug: string
  project_id: string
  heading_path: string
  score: number
}

// ============ 文件 ============

export interface FileMeta {
  id: string
  organization_id: string
  project_id: string | null
  owner_id: number
  original_name: string
  storage_key: string
  mime_type: string
  size: number
  purpose: string
  status: string
  parser_type: string | null
  chunk_count: number
  error_message: string | null
  created_at: string
  updated_at: string
}

// ============ 热点（保留首页） ============

export interface HotItem {
  title: string
  url: string
  description: string
  source: string
  extra: Record<string, unknown>
}

export interface HotspotResponse {
  github: HotItem[]
  bilibili: HotItem[]
  community: HotItem[]
}

/** 表格块内容结构 */
export interface TableBlockContent {
  headers: string[]
  rows: string[][]
}
