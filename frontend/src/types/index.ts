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

/** 认证响应 */
export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

/** 页面基础信息（不含 blocks） */
export interface PageRead {
  id: number
  workspace_id: number
  title: string
  icon: string | null
  category: string
  parent_id: number | null
  sort_order: number
  is_pinned: boolean
  created_at: string
  updated_at: string
}

/** 页面树节点 */
export interface PageTreeNode {
  id: number
  workspace_id: number
  title: string
  icon: string | null
  category: string
  parent_id: number | null
  sort_order: number
  is_pinned: boolean
  created_at: string
  updated_at: string
  children: PageTreeNode[]
  linked_children: PageTreeNode[]
}

/** Block */
export interface Block {
  id: number
  page_id: number
  type: string
  content: Record<string, unknown>
  sort_order: number
  created_at: string
  updated_at: string
}

/** 页面详情 */
export interface PageDetail {
  id: number
  workspace_id: number
  title: string
  icon: string | null
  category: string
  parent_id: number | null
  sort_order: number
  is_pinned: boolean
  created_at: string
  updated_at: string
  blocks: Block[]
}

/** 热点条目 */
export interface HotItem {
  title: string
  url: string
  description: string
  source: string
  extra: Record<string, unknown>
}

/** 热点聚合 */
export interface HotspotResponse {
  github: HotItem[]
  bilibili: HotItem[]
  community: HotItem[]
}
