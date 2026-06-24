import { defineStore } from 'pinia'
import { ref } from 'vue'
import { pagesApi, blocksApi } from '@/api/pages'
import type { Block, PageDetail, PageTreeNode, PageRead } from '@/types'

export const usePageStore = defineStore('page', () => {
  const tree = ref<PageTreeNode[]>([])
  const currentPage = ref<PageDetail | null>(null)
  const loading = ref(false)
  const searchQuery = ref('')
  const searchResults = ref<PageTreeNode[]>([])

  async function fetchTree() {
    const { data } = await pagesApi.tree()
    tree.value = data
  }

  async function fetchPage(pageId: number) {
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
    loading.value = true
    try {
      const { data } = await pagesApi.getBySlug(slug)
      currentPage.value = data
      return data
    } finally {
      loading.value = false
    }
  }

  /** 构建面包屑路径 */
  function getBreadcrumb(pageId: number): { id: number; slug: string; title: string }[] {
    const path: { id: number; slug: string; title: string }[] = []
    const pageMap = new Map<number, PageTreeNode>()
    function walk(nodes: PageTreeNode[]) {
      for (const n of nodes) {
        pageMap.set(n.id, n)
        if (n.children) walk(n.children)
        if (n.linked_children) walk(n.linked_children)
      }
    }
    walk(tree.value)
    let current: PageTreeNode | undefined = pageMap.get(pageId)
    while (current) {
      path.unshift({ id: current.id, slug: current.slug, title: current.title })
      if (current.parent_id) {
        current = pageMap.get(current.parent_id)
      } else {
        break
      }
    }
    return path
  }

  async function createPage(title = '无标题页面', icon = 'doc', parentId?: number) {
    const payload: { title: string; icon: string; parent_id?: number } = { title, icon }
    if (parentId) payload.parent_id = parentId
    const { data } = await pagesApi.create(payload)
    await fetchTree()
    return data
  }

  async function updatePage(pageId: number, payload: Record<string, unknown>) {
    const { data } = await pagesApi.update(pageId, payload)
    await fetchTree()
    if (currentPage.value?.id === pageId) {
      Object.assign(currentPage.value, data)
    }
    return data
  }

  async function renamePage(pageId: number, title: string) {
    return await updatePage(pageId, { title })
  }

  async function movePage(pageId: number, parentId: number | null) {
    await pagesApi.update(pageId, { parent_id: parentId })
    // 页面移动后同步引用该页面的 page_link 块
    await pagesApi.syncLinkBlocks(pageId)
    await fetchTree()
  }

  /** 同级页面拖拽排序：将 source 插入到 target 的上方或下方 */
  async function reorderPages(sourceId: number, targetId: number, position: 'above' | 'below') {
    // 从树中查找两个页面节点
    const allNodes: PageTreeNode[] = []
    function walk(nodes: PageTreeNode[]) {
      for (const n of nodes) {
        allNodes.push(n)
        if (n.children) walk(n.children)
        if (n.linked_children) walk(n.linked_children)
      }
    }
    walk(tree.value)

    const source = allNodes.find(n => n.id === sourceId)
    const target = allNodes.find(n => n.id === targetId)
    if (!source || !target) return

    // 获取 target 的所有同级节点，计算实际的 sort_order
    const targetParent = target.parent_id ?? 0
    const siblings = allNodes.filter(
      n => (n.parent_id ?? 0) === targetParent && n.id !== sourceId
    ).sort((a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0))

    const targetIdx = siblings.findIndex(n => n.id === targetId)
    if (targetIdx < 0) return

    let newOrder: number
    if (position === 'above') {
      // 插入到 target 之前
      if (targetIdx === 0) {
        newOrder = (target.sort_order ?? 0) - 1
      } else {
        const prevOrder = siblings[targetIdx - 1].sort_order ?? 0
        const tgtOrder = target.sort_order ?? 0
        newOrder = (prevOrder + tgtOrder) / 2
      }
    } else {
      // 插入到 target 之后
      if (targetIdx === siblings.length - 1) {
        newOrder = (target.sort_order ?? 0) + 1
      } else {
        const tgtOrder = target.sort_order ?? 0
        const nextOrder = siblings[targetIdx + 1].sort_order ?? 0
        newOrder = (tgtOrder + nextOrder) / 2
      }
    }

    // 直接调用 API（updatePage 内部会 fetchTree，这里避免重复调用）
    await pagesApi.update(sourceId, { sort_order: newOrder })
    await pagesApi.syncLinkBlocks(sourceId)
    await fetchTree()
  }

  async function deletePage(pageId: number) {
    await pagesApi.remove(pageId)
    if (currentPage.value?.id === pageId) {
      currentPage.value = null
    }
    await fetchTree()
  }

  async function duplicatePage(pageId: number): Promise<PageRead> {
    const { data } = await pagesApi.duplicate(pageId)
    await fetchTree()
    return data as unknown as PageRead
  }

  async function addBlock(pageId: number, type: string, content: Record<string, unknown> = {}) {
    const sortOrder = currentPage.value?.blocks.length ?? 0
    const { data } = await blocksApi.create(pageId, { type, content, sort_order: sortOrder })
    if (currentPage.value?.id === pageId) {
      currentPage.value.blocks.push(data)
    }
    await fetchTree()
    return data
  }

  /** 在指定索引处插入 Block（本地立即更新，后续需调用 reorderBlocks 同步排序） */
  async function insertBlockAt(pageId: number, index: number, type: string, content: Record<string, unknown> = {}) {
    const sortOrder = currentPage.value?.blocks.length ?? 0
    const { data } = await blocksApi.create(pageId, { type, content, sort_order: sortOrder })
    if (currentPage.value?.id === pageId) {
      currentPage.value.blocks.splice(index, 0, data)
    }
    return data
  }

  async function updateBlock(blockId: number, payload: Record<string, unknown>) {
    const { data } = await blocksApi.update(blockId, payload)
    if (currentPage.value) {
      const idx = currentPage.value.blocks.findIndex((b) => b.id === blockId)
      if (idx >= 0) currentPage.value.blocks[idx] = data
    }
    await fetchTree()
    return data
  }

  async function deleteBlock(blockId: number) {
    await blocksApi.remove(blockId)
    if (currentPage.value) {
      currentPage.value.blocks = currentPage.value.blocks.filter((b) => b.id !== blockId)
    }
    await fetchTree()
  }

  async function duplicateBlock(blockId: number) {
    const { data } = await blocksApi.duplicate(blockId)
    if (currentPage.value?.blocks.some(b => b.id === blockId)) {
      currentPage.value.blocks.push(data)
    }
    await fetchTree()
    return data
  }

  async function reorderBlocks(pageId: number, blockIds: number[]) {
    const { data } = await blocksApi.reorder(pageId, blockIds)
    if (currentPage.value?.id === pageId) {
      currentPage.value.blocks = data
    }
  }

  async function importToPage(pageId: number, content: string, format: 'html' | 'md') {
    const { data } = await blocksApi.importToPage(pageId, content, format)
    if (currentPage.value?.id === pageId) {
      currentPage.value.blocks = data
    }
    await fetchTree()
    return data
  }

  async function importPages(formData: FormData) {
    const { data } = await blocksApi.importPages(formData)
    await fetchTree()
    return data
  }

  async function searchPages(q: string) {
    searchQuery.value = q
    if (!q.trim()) {
      searchResults.value = []
      return
    }
    const { data } = await pagesApi.search(q)
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
    searchPages,
  }
})
