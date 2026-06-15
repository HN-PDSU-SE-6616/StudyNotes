<template>
  <div class="h-screen flex overflow-hidden">
    <NotesSidebar
      v-if="sidebarVisible"
      :active-id="activePageId"
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

const activePageId = computed(() => {
  const id = route.params.pageId
  return id ? Number(id) : null
})

onMounted(async () => {
  await pageStore.fetchTree()
  if (activePageId.value) {
    await pageStore.fetchPage(activePageId.value)
  }
})

watch(activePageId, async (id) => {
  if (id) await pageStore.fetchPage(id)
  else pageStore.currentPage = null
})

async function onSelectPage(id: number) {
  router.push(`/notes/${id}`)
}

async function onCreatePage() {
  const page = await pageStore.createPage()
  // 新页面添加2个默认占位 block
  await pageStore.addBlock(page.id, 'heading', { level: 1, text: '' })
  await pageStore.addBlock(page.id, 'paragraph', { text: '' })
  router.push(`/notes/${page.id}`)
}

async function onCreateSubPage(parentId: number) {
  const page = await pageStore.createSubPage(parentId)
  router.push(`/notes/${page.id}`)
}
</script>
