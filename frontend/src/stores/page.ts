import { defineStore } from 'pinia'
import { ref } from 'vue'
import { pagesApi, blocksApi } from '@/api/pages'
import { filesApi } from '@/api/files'
import { useOrgStore } from '@/stores/org'
import type { Block, PageDetail, PageTreeNode } from '@/types'

/**
 * 笔记内容 Store（沿用旧 page store 命名与方法，内部切换到 Note API + 项目上下文）
 */
export const usePageStore = defineStore('page', () => {
  const tree = ref<PageTreeNode[]>([])
  const currentPage = ref<PageDetail | null>(null)
  const loading = ref(false)
  const searchQuery = ref('')
  const searchResults = ref<PageTreeNode[]>([])

  /** 当前项目（来自 org store 上下文） */
  function projectId(): string {
    const orgStore = useOrgStore()
    if (!orgStore.activeProject) throw new Error('尚未选择项目')
    return orgStore.activeProject.id
  }

  async function fetchTree() {
    const pid = projectId()
    const { data } = await pagesApi.tree(pid)
    tree.value = data
  }

  async function fetchPage(pageId: string) {
    loading.value = true
    try {
      const { data } = await pagesApi.detail(pageId)
      currentPage.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  async function fetchPageBySlug(slug: string) {
    const pid = projectId()
    loading.value = true
    try {
      const { data } = await pagesApi.getBySlug(pid, slug)
      currentPage.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  /** 面包屑路径 */
  function getBreadcrumb(pageId: string): { id: string; slug: string; title: string }[] {
    const path: { id: string; slug: string; title: string }[] = []
    const map = new Map<string, PageTreeNode>()
    function walk(nodes: PageTreeNode[]) {
      for (const n of nodes) {
        map.set(n.id, n)
        if (n.children) walk(n.children)
        if (n.linked_children) walk(n.linked_children)
      }
    }
    walk(tree.value)
    let current = map.get(pageId)
    while (current) {
      path.unshift({ id: current.id, slug: current.slug, title: current.title })
      current = current.parent_id ? map.get(current.parent_id) : undefined
    }
    return path
  }

  async function createPage(title = '无标题页面', icon = 'doc', parentId?: string) {
    const pid = projectId()
    const payload: { title: string; icon: string; parent_id?: string | null } = { title, icon }
    if (parentId) payload.parent_id = parentId
    const { data } = await pagesApi.create(pid, payload)
    await fetchTree()
    return data
  }

  async function updatePage(pageId: string, payload: Record<string, unknown>) {
    const { data } = await pagesApi.update(pageId, payload)
    await fetchTree()
    if (currentPage.value?.id === pageId) {
      Object.assign(currentPage.value, data)
    }
    return data
  }

  async function renamePage(pageId: string, title: string) {
    return await updatePage(pageId, { title })
  }

  async function movePage(pageId: string, parentId: string | null) {
    await pagesApi.update(pageId, { parent_id: parentId })
    await pagesApi.syncLinkBlocks(pageId)
    await fetchTree()
  }

  /** 同级拖拽排序 */
  async function reorderPages(sourceId: string, targetId: string, position: 'above' | 'below') {
    const allNodes: PageTreeNode[] = []
    function walk(nodes: PageTreeNode[]) {
      for (const n of nodes) {
        allNodes.push(n)
        if (n.children) walk(n.children)
        if (n.linked_children) walk(n.linked_children)
      }
    }
    walk(tree.value)
    const source = allNodes.find((n) => n.id === sourceId)
    const target = allNodes.find((n) => n.id === targetId)
    if (!source || !target) return

    const siblings = allNodes
      .filter((n) => (n.parent_id ?? null) === (target.parent_id ?? null) && n.id !== sourceId)
      .sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))
    const idx = siblings.findIndex((n) => n.id === targetId)
    if (idx < 0) return

    let newOrder: number
    if (position === 'above') {
      newOrder = idx === 0 ? (target.sort_order ?? 0) - 1 : (siblings[idx - 1].sort_order + target.sort_order) / 2
    } else {
      newOrder =
        idx === siblings.length - 1
          ? (target.sort_order ?? 0) + 1
          : (target.sort_order + siblings[idx + 1].sort_order) / 2
    }
    await pagesApi.update(sourceId, { sort_order: newOrder })
    await pagesApi.syncLinkBlocks(sourceId)
    await fetchTree()
  }

  async function deletePage(pageId: string) {
    await pagesApi.remove(pageId)
    if (currentPage.value?.id === pageId) currentPage.value = null
    await fetchTree()
  }

  async function duplicatePage(pageId: string) {
    const { data } = await pagesApi.duplicate(pageId)
    await fetchTree()
    return data
  }

  async function addBlock(pageId: string, type: string, content: Record<string, unknown> = {}) {
    const sortOrder = currentPage.value?.blocks.length ?? 0
    const { data } = await blocksApi.create(pageId, { type, content, sort_order: sortOrder })
    if (currentPage.value?.id === pageId) currentPage.value.blocks.push(data)
    await fetchTree()
    return data
  }

  /** 在指定索引处插入块 */
  async function insertBlockAt(
    pageId: string,
    index: number,
    type: string,
    content: Record<string, unknown> = {},
  ) {
    const sortOrder = currentPage.value?.blocks.length ?? 0
    const { data } = await blocksApi.create(pageId, { type, content, sort_order: sortOrder })
    if (currentPage.value?.id === pageId) {
      currentPage.value.blocks.splice(index, 0, data)
    }
    return data
  }

  async function updateBlock(blockId: string, payload: Record<string, unknown>) {
    const { data } = await blocksApi.update(blockId, payload)
    if (currentPage.value) {
      const idx = currentPage.value.blocks.findIndex((b) => b.id === blockId)
      if (idx >= 0) currentPage.value.blocks[idx] = data
    }
    await fetchTree()
    return data
  }

  async function deleteBlock(blockId: string) {
    await blocksApi.remove(blockId)
    if (currentPage.value) {
      currentPage.value.blocks = currentPage.value.blocks.filter((b) => b.id !== blockId)
    }
    await fetchTree()
  }

  async function duplicateBlock(blockId: string) {
    const { data } = await blocksApi.duplicate(blockId)
    if (currentPage.value?.blocks.some((b) => b.id === blockId)) {
      currentPage.value.blocks.push(data)
    }
    await fetchTree()
    return data
  }

  async function reorderBlocks(pageId: string, blockIds: string[]) {
    const { data } = await blocksApi.reorder(pageId, blockIds)
    if (currentPage.value?.id === pageId) currentPage.value.blocks = data
  }

  async function importToPage(pageId: string, content: string, format: 'html' | 'md') {
    const { data } = await blocksApi.importToNote(pageId, content, format)
    if (currentPage.value?.id === pageId) currentPage.value.blocks = data
    await fetchTree()
    return data
  }

  /** 兼容旧“目录/文件导入”：逐文件上传为文档并轮询解析 */
  async function importPages(formData: FormData) {
    const pid = projectId()
    const files = Array.from(formData.getAll('files')) as unknown as File[]
    const list = files.length ? files : (Array.from(formData.entries()).map(([, v]) => v) as unknown as File[])
    const results: unknown[] = []
    for (const file of list) {
      if (!(file instanceof File)) continue
      const { data } = await filesApi.upload(pid, file, 'document')
      results.push(data)
    }
    await fetchTree()
    return results
  }

  async function importFiles(fileList: File[]) {
    const pid = projectId()
    const results: unknown[] = []
    for (const file of fileList) {
      const { data } = await filesApi.upload(pid, file, 'document')
      results.push(data)
    }
    await fetchTree()
    return results
  }

  async function searchPages(q: string) {
    searchQuery.value = q
    if (!q.trim()) {
      searchResults.value = []
      return
    }
    const pid = projectId()
    const { data } = await pagesApi.search(pid, q)
    searchResults.value = data as unknown as PageTreeNode[]
  }

  return {
    tree,
    currentPage,
    loading,
    searchQuery,
    searchResults,
    fetchTree,
    fetchPage,
    fetchPageBySlug,
    getBreadcrumb,
    createPage,
    updatePage,
    renamePage,
    movePage,
    reorderPages,
    deletePage,
    duplicatePage,
    addBlock,
    insertBlockAt,
    updateBlock,
    deleteBlock,
    duplicateBlock,
    reorderBlocks,
    importToPage,
    importPages,
    importFiles,
    searchPages,
  }
})
