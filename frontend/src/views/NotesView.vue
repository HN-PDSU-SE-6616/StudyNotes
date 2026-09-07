<template>
  <div class="h-screen flex overflow-hidden bg-white">
    <!-- ===== 桌面侧边栏 ===== -->
    <aside class="hidden md:flex w-72 shrink-0 border-r border-slate-200 flex-col bg-white">
      <ContextBar @navigate-home="goHome" @create-project="openCreateProject" />
      <NotesSidebar
        v-if="!orgStore.loading && orgStore.activeProject"
        :active-id="pageStore.currentPage?.id ?? null"
        @select="onSelectPage"
        @create="onCreatePage"
      />
      <div v-else class="flex-1 flex items-center justify-center text-sm text-slate-400">
        加载中…
      </div>
    </aside>

    <!-- ===== 移动端抽屉 ===== -->
    <Transition name="fade">
      <div
        v-if="mobileDrawer"
        class="fixed inset-0 z-40 bg-black/40 md:hidden"
        @click="mobileDrawer = false"
      />
    </Transition>
    <Transition name="slide-left">
      <aside
        v-if="mobileDrawer"
        class="fixed left-0 top-0 bottom-0 z-50 w-80 max-w-[85vw] bg-white shadow-2xl md:hidden flex flex-col"
      >
        <ContextBar @navigate-home="goHome" @create-project="openCreateProject" />
        <NotesSidebar
          v-if="orgStore.activeProject"
          :active-id="pageStore.currentPage?.id ?? null"
          @select="onSelectPageMobile"
          @create="onCreatePageMobile"
        />
      </aside>
    </Transition>

    <!-- ===== 主区域 ===== -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶栏（移动端） -->
      <header class="h-12 border-b border-slate-100 flex items-center gap-2 px-3 md:hidden shrink-0">
        <button
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
          @click="mobileDrawer = true"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div class="flex-1 min-w-0">
          <div class="text-sm font-semibold text-slate-700 truncate">{{ orgStore.activeProject?.name || '知识库' }}</div>
          <div class="text-[10px] text-slate-400 truncate">{{ orgStore.activeOrg?.name }}</div>
        </div>
        <button
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
          :class="{ 'text-brand-600 bg-brand-50': aiOpen }"
          title="AI 问答"
          @click="aiOpen = !aiOpen"
        >
          <svg class="w-4.5 h-4.5 w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h8M8 14h4M9 17H7a2 2 0 01-2-2V5a2 2 0 012-2h10a2 2 0 012 2v10a2 2 0 01-2 2h-2l-4 4v-4" />
          </svg>
        </button>
      </header>

      <PageEditor
        v-if="orgStore.activeProject"
        @navigate="onSelectPage"
        @toggle-sidebar="mobileDrawer = !mobileDrawer"
      />
      <div v-else class="flex-1 flex items-center justify-center text-slate-400 text-sm">
        请先选择或创建一个项目
      </div>
    </div>

    <!-- ===== AI 问答抽屉（右侧） ===== -->
    <Transition name="slide-right">
      <div
        v-if="aiOpen"
        class="fixed right-0 top-0 bottom-0 z-50 w-[min(92vw,420px)] shadow-2xl md:static md:z-auto md:shadow-none md:border-l md:border-slate-200"
      >
        <RagPanel @close="aiOpen = false" @open-source="openSource" />
      </div>
    </Transition>
    <button
      v-if="!aiOpen && orgStore.activeProject"
      class="hidden md:flex fixed bottom-6 right-6 z-30 items-center gap-2 px-4 py-3 rounded-2xl bg-brand-600 text-white text-sm font-medium shadow-lg hover:bg-brand-700 transition-colors"
      @click="aiOpen = true"
    >
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h8M8 14h4M9 17H7a2 2 0 01-2-2V5a2 2 0 012-2h10a2 2 0 012 2v10a2 2 0 01-2 2h-2l-4 4v-4" />
      </svg>
      AI 问答
    </button>

    <!-- 创建项目弹窗 -->
    <Teleport to="body">
      <div v-if="createDialog" class="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4" @click.self="createDialog = false">
        <div class="bg-white rounded-2xl p-6 w-full max-w-sm shadow-xl">
          <h3 class="text-lg font-semibold text-slate-800 mb-4">新建项目</h3>
          <input
            v-model="newProjectName"
            class="w-full px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30"
            placeholder="项目名称"
          />
          <div class="flex justify-end gap-3 mt-5">
            <button class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl" @click="createDialog = false">取消</button>
            <button class="px-4 py-2 text-sm bg-brand-600 text-white rounded-xl hover:bg-brand-700" @click="confirmCreateProject">创建</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { usePageStore } from '@/stores/page'
import { useOrgStore } from '@/stores/org'
import { orgsApi } from '@/api/orgs'
import NotesSidebar from '@/components/notes/NotesSidebar.vue'
import PageEditor from '@/components/notes/PageEditor.vue'
import RagPanel from '@/components/rag/RagPanel.vue'
import ContextBar from '@/components/notes/ContextBar.vue'
import type { PageTreeNode, RagSource } from '@/types'

const route = useRoute()
const router = useRouter()
const pageStore = usePageStore()
const orgStore = useOrgStore()

const mobileDrawer = ref(false)
const aiOpen = ref(false)
const createDialog = ref(false)
const newProjectName = ref('')

const activeSlug = computed(() => {
  const s = route.params.slug
  return typeof s === 'string' && s ? s : null
})

const requestedProject = computed(() => {
  const q = route.query.project
  return typeof q === 'string' && q ? q : undefined
})

async function ensureContext() {
  await orgStore.ensureContext(undefined, requestedProject.value)
}

async function loadTreeAndNote() {
  await ensureContext()
  await pageStore.fetchTree()
  const slug = activeSlug.value
  if (slug) {
    await pageStore.fetchPageBySlug(slug)
  } else {
    pageStore.currentPage = null
  }
}

onMounted(async () => {
  await loadTreeAndNote()
  await scrollToAnchor()
})

watch(
  () => [route.params.slug, route.query.project],
  async () => {
    await loadTreeAndNote()
    await scrollToAnchor()
  },
)

/** 引用跳转：按 heading 文本滚动并高亮 */
async function scrollToAnchor() {
  const anchor = route.query.anchor
  if (typeof anchor !== 'string' || !anchor) return
  await nextTick()
  await new Promise((r) => setTimeout(r, 150))
  const segments = anchor.split('/').filter(Boolean)
  const targetText = segments[segments.length - 1]
  highlightText(targetText)
}

function highlightText(text: string) {
  if (!text) return
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT)
  let node: Node | null
  while ((node = walker.nextNode())) {
    const el = node as HTMLElement
    const tag = el.tagName
    const isHeading = /^H[1-6]$/.test(tag)
    const txt = (el.textContent || '').trim()
    if (txt && txt.length <= 160 && (txt === text || txt.endsWith(text) || txt.includes(text))) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('rag-flash')
      setTimeout(() => el.classList.remove('rag-flash'), 2000)
      break
    }
    // 优先扫描标题元素后，其次普通元素
    if (isHeading && txt && txt.includes(text)) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('rag-flash')
      setTimeout(() => el.classList.remove('rag-flash'), 2000)
      break
    }
  }
}

function notePath(slug: string, projectId?: string): string {
  const pid = projectId || orgStore.activeProject?.id
  return pid ? `/notes/${slug}?project=${pid}` : `/notes/${slug}`
}

function onSelectPage(id: string) {
  const page = findPageById(pageStore.tree, id)
  if (page?.slug) router.push(notePath(page.slug))
}

function onSelectPageMobile(id: string) {
  onSelectPage(id)
  mobileDrawer.value = false
}

async function onCreatePage(parentId?: string) {
  const page = await pageStore.createPage(undefined, undefined, parentId)
  router.push(notePath(page.slug))
}

async function onCreatePageMobile(parentId?: string) {
  await onCreatePage(parentId)
  mobileDrawer.value = false
}

async function openSource(src: RagSource) {
  const target = notePath(src.slug, src.project_id)
  // 同项目直接携带 anchor 跳转
  if (src.project_id === orgStore.activeProject?.id) {
    router.push({ path: `/notes/${src.slug}`, query: { project: src.project_id, anchor: src.anchor || src.heading_path } })
  } else {
    router.push({ path: '/notes', query: { project: src.project_id } })
  }
  mobileDrawer.value = false
}

function findPageById(nodes: PageTreeNode[], id: string): PageTreeNode | null {
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

function goHome() {
  router.push('/')
}

function openCreateProject() {
  createDialog.value = true
  newProjectName.value = ''
}

async function confirmCreateProject() {
  const name = newProjectName.value.trim()
  const orgId = orgStore.activeOrg?.id
  if (!name || !orgId) return
  const { data } = await orgsApi.createProject(orgId, { name })
  createDialog.value = false
  await orgStore.selectOrg(orgStore.activeOrg!)
  orgStore.selectProject(data)
  pageStore.currentPage = null
  router.push('/notes')
}
</script>

<style>
.rag-flash {
  animation: rag-flash 1.2s ease;
  border-radius: 6px;
}
@keyframes rag-flash {
  0%,
  100% {
    background: transparent;
  }
  30%,
  70% {
    background: rgba(14, 165, 233, 0.18);
    box-shadow: 0 0 0 4px rgba(14, 165, 233, 0.12);
  }
}
</style>
