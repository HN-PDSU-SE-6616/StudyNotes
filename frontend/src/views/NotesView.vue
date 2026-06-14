<template>
  <div class="h-screen flex overflow-hidden">
    <NotesSidebar
      :active-id="activePageId"
      @select="onSelectPage"
      @create="onCreatePage"
    />
    <PageEditor @navigate="onSelectPage" />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePageStore } from '@/stores/page'
import NotesSidebar from '@/components/notes/NotesSidebar.vue'
import PageEditor from '@/components/notes/PageEditor.vue'

const route = useRoute()
const router = useRouter()
const pageStore = usePageStore()

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
  router.push(`/notes/${page.id}`)
}
</script>
