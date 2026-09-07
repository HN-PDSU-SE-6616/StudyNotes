<template>
  <div class="h-screen flex overflow-hidden bg-slate-50">
    <aside class="hidden md:flex w-64 shrink-0 border-r border-slate-200 bg-white flex-col p-4">
      <div class="flex items-center gap-2 mb-6">
        <span class="w-8 h-8 rounded-xl bg-brand-50 flex items-center justify-center">
          <svg class="w-4 h-4 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
          </svg>
        </span>
        <h2 class="font-semibold text-slate-800">关系图</h2>
      </div>
      <router-link to="/" class="text-sm text-slate-500 hover:text-brand-600 mb-3">← 工作台</router-link>
      <router-link :to="`/notes?project=${orgStore.activeProject?.id ?? ''}`" class="text-sm text-slate-500 hover:text-brand-600">
        ← 进入笔记
      </router-link>
    </aside>

    <main class="flex-1 overflow-y-auto p-4 md:p-8">
      <div class="bg-white rounded-2xl border border-slate-200 p-5 mb-6">
        <div class="text-lg font-bold text-slate-800 mb-1">项目：{{ orgStore.activeProject?.name || '未选择' }}</div>
        <div class="text-sm text-slate-400">共 {{ nodes.length }} 个节点 / {{ edges.length }} 条关系（父子 + 笔记链接）</div>
      </div>

      <div v-if="loading" class="text-sm text-slate-400 text-center py-16">加载中…</div>

      <div v-else class="grid gap-3 md:grid-cols-3">
        <button
          v-for="n in nodes"
          :key="String(n.id)"
          class="bg-white rounded-2xl border border-slate-200 p-4 text-left hover:border-brand-300 hover:shadow-md transition-all"
          @click="openNote(n)"
        >
          <div class="text-sm font-medium text-slate-700 truncate">{{ n.title }}</div>
          <div class="text-[10px] text-slate-400 mt-1">id: {{ n.id }}</div>
        </button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { pagesApi } from '@/api/pages'
import { useOrgStore } from '@/stores/org'

interface GraphNode {
  id: string | number
  title: string
  icon?: string | null
}

const router = useRouter()
const orgStore = useOrgStore()
const nodes = ref<GraphNode[]>([])
const edges = ref<{ source: string | number; target: string | number }[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    if (!orgStore.activeProject) await orgStore.ensureContext()
    const pid = orgStore.activeProject?.id
    if (!pid) return
    const { data } = await pagesApi.graph(pid)
    nodes.value = (data.nodes || []) as GraphNode[]
    edges.value = (data.edges || []) as { source: string | number; target: string | number }[]
  } finally {
    loading.value = false
  }
})

function openNote(n: GraphNode) {
  router.push({ path: `/notes/${String(n.id)}`, query: { project: orgStore.activeProject?.id } })
}
</script>
