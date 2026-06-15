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

  async function createPage(title = '无标题页面') {
    const { data } = await pagesApi.create({ title, icon: '📄' })
    await fetchTree()
    return data
  }

  async function createSubPage(parentId: number, title = '无标题子页面') {
    const { data } = await pagesApi.create({ title, icon: '📄', parent_id: parentId })
    // 在父页面末尾添加 page_link block
    await addBlock(parentId, 'page_link', { page_id: data.id, title })
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
    return await updatePage(pageId, { parent_id: parentId })
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
    createPage,
    createSubPage,
    updatePage,
    renamePage,
    movePage,
    deletePage,
    duplicatePage,
    addBlock,
    updateBlock,
    deleteBlock,
    duplicateBlock,
    reorderBlocks,
    importToPage,
    searchPages,
  }
})
