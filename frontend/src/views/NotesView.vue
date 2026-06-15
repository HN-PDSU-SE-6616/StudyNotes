<template>
  <div class="h-screen flex overflow-hidden">
    <NotesSidebar
      v-if="sidebarVisible"
      :active-id="pageStore.currentPage?.id ?? null"
      @select="onSelectPage"
      @create="onCreatePage"
      @create-sub-page="onCreateSubPage"
    />
    <PageEditor
      @navigate="onSelectPage"
      @toggle-sidebar="sidebarVisible = !sidebarVisible"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePageStore } from '@/stores/page'
import NotesSidebar from '@/components/notes/NotesSidebar.vue'
import PageEditor from '@/components/notes/PageEditor.vue'

const route = useRoute()
const router = useRouter()
const pageStore = usePageStore()
const sidebarVisible = ref(true)

const activeSlug = computed(() => {
  const s = route.params.slug
  return typeof s === 'string' && s ? s : null
})

onMounted(async () => {
  await pageStore.fetchTree()
  if (activeSlug.value) {
    await pageStore.fetchPageBySlug(activeSlug.value)
  }
})

watch(activeSlug, async (slug) => {
  if (slug) await pageStore.fetchPageBySlug(slug)
  else pageStore.currentPage = null
})

async function onSelectPage(id: number) {
  // 从 tree 中查找对应 slug
  const page = findPageById(pageStore.tree, id)
  if (page?.slug) {
    router.push(`/notes/${page.slug}`)
  }
}

function findPageById(nodes: import('@/types').PageTreeNode[], id: number): import('@/types').PageTreeNode | null {
  for (const n of nodes) {
    if (n.id === id) return n
    if (n.children) {
      const found = findPageById(n.children, id)
      if (found) return found
    }
    if (n.linked_children) {
      const found = findPageById(n.linked_children, id)
      if (found) return found
    }
  }
  return null
}

async function onCreatePage() {
  const page = await pageStore.createPage()
  router.push(`/notes/${page.slug}`)
}

async function onCreateSubPage(parentId: number) {
  const page = await pageStore.createSubPage(parentId)
  router.push(`/notes/${page.slug}`)
}
</script>
