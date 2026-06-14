import { defineStore } from 'pinia'
import { ref } from 'vue'
import { pagesApi, blocksApi } from '@/api/pages'
import type { Block, PageDetail, PageTreeNode } from '@/types'

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
    addBlock,
    updateBlock,
    searchPages,
  }
})
