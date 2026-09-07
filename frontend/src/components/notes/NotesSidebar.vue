<template>
  <aside class="w-72 bg-white border-r border-slate-200 flex flex-col h-full shrink-0">
    <!-- 用户信息 -->
    <div class="p-4 border-b border-slate-100">
      <UserAvatar :name="auth.displayName" :url="auth.avatarUrl" size="lg" subtitle="我的知识库" />
    </div>

    <!-- 功能工具栏 -->
    <div class="p-3 border-b border-slate-100 space-y-1">
      <div class="relative">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          v-model="searchInput"
          type="text"
          placeholder="全局搜索..."
          class="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
          @input="onSearch"
        />
      </div>

      <div v-if="pageStore.searchResults.length" class="mt-2 max-h-32 overflow-y-auto space-y-0.5">
        <button
          v-for="r in pageStore.searchResults"
          :key="r.id"
          class="w-full text-left px-2 py-1.5 text-sm rounded-lg hover:bg-slate-100 truncate"
          @click="$emit('select', r.id)"
        >
          <span v-if="getSidebarIconPaths(r.icon)" class="shrink-0 w-4 h-4 text-slate-500 inline-block align-middle">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4">
              <path v-for="(p, pi) in getSidebarIconPaths(r.icon)!" :key="pi" :d="p.d" :fill="p.fill || undefined" :stroke-width="p.strokeWidth || undefined" />
            </svg>
          </span>
          <span v-else>{{ r.icon || '📄' }}</span> {{ r.title }}
        </button>
      </div>

      <button class="nav-item w-full" @click="$router.push('/graph')">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>
        页面关系图
      </button>
      <button class="nav-item w-full opacity-50 cursor-not-allowed">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" /></svg>
        消息箱
      </button>
      <button class="nav-item w-full opacity-50 cursor-not-allowed">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 12.75a.75.75 0 110-1.5.75.75 0 010 1.5zM12 18.75a.75.75 0 110-1.5.75.75 0 010 1.5z" /></svg>
        更多操作
      </button>
    </div>

    <!-- 我的页面 -->
    <div class="flex-1 overflow-y-auto p-3">
      <div class="flex items-center justify-between mb-2 px-2">
        <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">我的页面</span>
        <div class="flex items-center gap-1">
          <button
            class="px-2 py-1 text-[11px] rounded-lg hover:bg-red-50 text-red-500 transition-colors"
            title="清理误导入：批量/全部删除"
            @click="openBatchPanel"
          >
            批量删除
          </button>
          <button
            class="w-6 h-6 flex items-center justify-center rounded-lg hover:bg-brand-50 text-brand-600 transition-colors"
            title="新增页面"
            @click="$emit('create')"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
          </button>
        </div>
      </div>

      <!-- 批量管理模式工具条 -->
      <div v-if="batchOpen" class="mb-2 px-2 py-1.5 rounded-lg bg-slate-50 border border-slate-200 flex items-center gap-2 text-xs">
        <span class="font-semibold text-slate-600">已选 {{ checkedIds.length }}</span>
        <button class="text-brand-600 hover:underline" @click="selectAllInTree">全选</button>
        <button class="text-slate-500 hover:underline" @click="checkedIds = []">清空</button>
        <span class="flex-1" />
        <button
          class="px-2 py-1 rounded-lg bg-red-600 text-white hover:bg-red-700 disabled:opacity-40"
          :disabled="!checkedIds.length"
          @click="confirmBatchDelete"
        >
          删除所选
        </button>
      </div>

      <!-- 危险操作：清空整个项目 -->
      <div v-if="!batchOpen && pageStore.tree.length" class="mb-2 px-2">
        <button class="text-[11px] text-red-400 hover:text-red-600 hover:underline" @click="confirmClearProject">
          ⚠ 清空此项目的全部页面（导入失误后整体清理）
        </button>
      </div>

      <div v-if="!pageStore.tree.length" class="text-center py-8 text-sm text-slate-400">
        <p>还没有页面</p>
        <button class="mt-2 text-brand-600 hover:underline" @click="$emit('create')">创建第一个页面</button>
      </div>

      <PageTreeNode
        v-for="node in pageStore.tree"
        :key="node.id"
        :node="node"
        :active-id="batchOpen ? '' : activeId"
        :all-pages="flatPages"
        :batch-open="batchOpen"
        :checked-ids="checkedIds"
        @select="onTreeNodeClick"
        @action="handleAction"
      />
    </div>

    <!-- 删除确认弹窗 -->
    <Teleport to="body">
      <div v-if="deleteTarget" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="deleteTarget = null">
        <div class="bg-white rounded-2xl p-6 w-96 shadow-xl">
          <h3 class="text-lg font-semibold text-slate-800 mb-2">删除页面</h3>
          <p class="text-sm text-slate-500 mb-6">
            确定要删除「{{ deleteTarget.title }}」吗？此操作将同时删除页面内的所有 Block 和链接关系，且不可恢复。
          </p>
          <div class="flex justify-end gap-3">
            <button class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl transition-colors" @click="deleteTarget = null">取消</button>
            <button class="px-4 py-2 text-sm bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors" @click="confirmDelete">确认删除</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 底部返回首页 -->
    <div class="p-3 border-t border-slate-100">
      <router-link to="/" class="nav-item w-full">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75" /></svg>
        返回首页
      </router-link>
    </div>

    <!-- 隐藏的文件导入输入 -->
    <!-- 目录选择 -->
    <input
      ref="dirInput"
      type="file"
      webkitdirectory
      class="hidden"
      @change="onImportDir"
    />
    <!-- 文件多选 -->
    <input
      ref="fileInput"
      type="file"
      accept=".md,.html,.htm,.txt,.csv,.log,.py,.js,.jsx,.ts,.tsx,.css,.scss,.less,.java,.c,.cpp,.h,.go,.rs,.rb,.php,.r,.swift,.json,.yaml,.yml,.xml,.sql,.sh,.bash,.bat,.ps1,.ini,.cfg,.conf,.xlsx,.xls,.docx,.pdf,.pptx,.ppt,.xmind,.png,.jpg,.jpeg,.gif,.webp,.svg,.bmp,.ico"
      multiple
      class="hidden"
      @change="onImportFiles"
    />

    <!-- 导入选择弹窗 -->
    <Teleport to="body">
      <div v-if="importDialogOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="importDialogOpen = false">
        <div class="bg-white rounded-2xl p-6 w-96 shadow-xl">
          <h3 class="text-lg font-semibold text-slate-800 mb-2">导入目录/文件</h3>
          <p class="text-sm text-slate-500 mb-5">选择导入方式。目录导入会递归处理子目录结构。</p>
          <div v-if="importTargetId" class="mb-4 px-3 py-2 rounded-lg bg-brand-50 text-xs text-brand-700 leading-relaxed">
            导入目标：当前页面。目录内若存在<b>与当前页面同名</b>的文件，内容将<b>追加</b>到该页面（重复导入会自动跳过）；
            未找到同名文件时当前页面保持不变，其余内容按目录结构建为子页面。
          </div>
          <div class="space-y-3">
            <button
              class="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-200 hover:bg-brand-50 hover:border-brand-300 transition-colors text-left"
              @click="selectDirectory"
            >
              <span class="text-xl">📁</span>
              <div>
                <div class="text-sm font-medium text-slate-700">导入目录</div>
                <div class="text-xs text-slate-400">选择整个文件夹，递归导入子目录</div>
              </div>
            </button>
            <button
              class="w-full flex items-center gap-3 px-4 py-2.5 rounded-xl border border-slate-200 hover:bg-brand-50 hover:border-brand-300 transition-colors text-left"
              @click="selectFiles"
            >
              <span class="text-xl">📄</span>
              <div>
                <div class="text-sm font-medium text-slate-700">导入文件</div>
                <div class="text-xs text-slate-400">选择一个或多个 .md / .html 文件</div>
              </div>
            </button>
          </div>
          <button class="mt-4 w-full py-2 text-sm text-slate-500 hover:text-slate-700 transition-colors" @click="importDialogOpen = false">取消</button>
        </div>
      </div>
    </Teleport>
    <!-- 导入加载中遮罩 -->
    <Teleport to="body">
      <div v-if="importing" class="fixed inset-0 z-50 flex items-center justify-center bg-black/20">
        <div class="bg-white rounded-2xl px-8 py-6 shadow-xl flex items-center gap-3">
          <div class="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span class="text-sm text-slate-600">正在导入，请稍候...</span>
        </div>
      </div>
    </Teleport>
  </aside>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePageStore } from '@/stores/page'
import { pagesApi } from '@/api/pages'
import type { ImportResponse } from '@/api/imports'
import type { PageTreeNode as PageTreeNodeType } from '@/types'
import UserAvatar from '@/components/common/UserAvatar.vue'
import PageTreeNode from './PageTreeNode.vue'

// Shared SVG icon path lookup (kept in sync with PageEditor/PageTreeNode)
const sidebarIconLib: Record<string, { d: string; fill?: string; strokeWidth?: string }[]> = {
  doc: [{ d: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z' }, { d: 'M14 2v6h6' }, { d: 'M16 13H8' }, { d: 'M16 17H8' }, { d: 'M10 9H8' }],
  note: [{ d: 'M11 5H6a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-7' }, { d: 'M18.375 2.625a2.121 2.121 0 113 3L12 15l-4 1 1-4 9.375-9.375z' }],
  star: [{ d: 'M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z' }],
  code: [{ d: 'M16 18l6-6-6-6' }, { d: 'M8 6l-6 6 6 6' }],
  book: [{ d: 'M4 19.5A2.5 2.5 0 016.5 17H20' }, { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' }],
  gear: [{ d: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z' }, { d: 'M15 12a3 3 0 11-6 0 3 3 0 016 0z' }],
  chart: [{ d: 'M3 3v18h18' }, { d: 'M7 16l4-8 4 4 4-6' }],
  folder: [{ d: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6.465a1 1 0 01-.832-.445l-1.11-1.664A2 2 0 009.535 4H5a2 2 0 00-2 2z' }],
  lightbulb: [{ d: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a1 1 0 01-1 1h-2a1 1 0 01-1-1v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' }],
  pin: [{ d: 'M15 10.5a3 3 0 11-6 0 3 3 0 016 0z' }, { d: 'M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 0115 0z' }],
  target: [{ d: 'M12 12m-1 0a1 1 0 102 0 1 1 0 10-2 0' }, { d: 'M12 12m-5 0a5 5 0 1010 0 5 5 0 10-10 0' }, { d: 'M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0' }],
  rocket: [{ d: 'M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z' }, { d: 'M12 15l-3-3a22 22 0 012.133-6.009A8.5 8.5 0 0115 4.357M15 4.357A8.5 8.5 0 0121 3a8.5 8.5 0 01-1.357 6A22 22 0 0115 12' }, { d: 'M9 15l-5 5' }, { d: 'M15 9l5-5' }],
  shield: [{ d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' }, { d: 'M9 12l2 2 4-4' }],
  database: [{ d: 'M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3' }, { d: 'M4 7v6c0 1.657 3.582 3 8 3s8-1.343 8-3V7' }, { d: 'M4 7v6c0 1.657 3.582 3 8 3s8-1.343 8-3' }],
  cloud: [{ d: 'M17.5 19H9a7 7 0 116.71-9h1.79a4.5 4.5 0 110 9z' }],
  heart: [{ d: 'M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z' }],
}
function getSidebarIconPaths(iconValue: string | null | undefined): { d: string; fill?: string; strokeWidth?: string }[] | null {
  if (!iconValue) return null
  return sidebarIconLib[iconValue] || null
}

defineProps<{ activeId?: number | null }>()
const emit = defineEmits<{ select: [id: number]; create: [parentId?: number] }>()

const auth = useAuthStore()
const pageStore = usePageStore()
const router = useRouter()
const searchInput = ref('')

// ---------- 批量删除 / 清空项目 ----------
const batchOpen = ref(false)
const checkedIds = ref<string[]>([])

function openBatchPanel() {
  batchOpen.value = !batchOpen.value
  checkedIds.value = []
}

function toggleNode(id: string) {
  const i = checkedIds.value.indexOf(id)
  if (i >= 0) checkedIds.value.splice(i, 1)
  else checkedIds.value.push(id)
}

function onTreeNodeClick(id: string) {
  if (batchOpen.value) toggleNode(id)
  else emit('select', id)
}

function selectAllInTree() {
  checkedIds.value = flatPages.value.map((n) => n.id)
}

async function confirmBatchDelete() {
  if (!checkedIds.value.length) return
  const ok = window.confirm(`确定删除选中的 ${checkedIds.value.length} 个页面吗？\n每个页面会连同其子页面一起删除，不可恢复。`)
  if (!ok) return
  const { data } = await pagesApi.batchDelete(checkedIds.value)
  await pageStore.fetchTree()
  checkedIds.value = []
  batchOpen.value = false
  const msg = `已删除 ${data.deleted_count} 个页面` + (data.failed.length ? `，${data.failed.length} 个无权限或不存在` : '')
  alert(msg)
}

async function confirmClearProject() {
  const ok = window.confirm('确定清空此项目的全部页面吗？\n所有页面及其子页面将被永久删除，不可恢复。')
  if (!ok) return
  const { data } = await pagesApi.clearProject(pageStore.projectId())
  await pageStore.fetchTree()
  pageStore.currentPage = null
  alert(`已清空：删除 ${data.deleted_roots} 棵根页面树，共 ${data.notes_removed} 个页面`)
}


// 文件导入
const dirInput = ref<HTMLInputElement>()
const fileInput = ref<HTMLInputElement>()
const importDialogOpen = ref(false)
const importTargetId = ref<string>('')
const importing = ref(false)

function triggerImport(pageId: string | number) {
  importTargetId.value = pageId ? String(pageId) : ''
  importDialogOpen.value = true
}

function selectDirectory() {
  importDialogOpen.value = false
  dirInput.value?.click()
}

function selectFiles() {
  importDialogOpen.value = false
  fileInput.value?.click()
}

async function onImportDir(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return
  await uploadImportFiles(files)
  input.value = ''
}

async function onImportFiles(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files || files.length === 0) return
  await uploadImportFiles(files)
  input.value = ''
}

async function uploadImportFiles(fileList: FileList) {
  const formData = new FormData()
  // 指定目标笔记时：顶层文档合并进该笔记，子目录作为其子笔记
  if (importTargetId.value) {
    formData.append('target_note_id', importTargetId.value)
  }

  for (let i = 0; i < fileList.length; i++) {
    const f = fileList[i]
    // webkitRelativePath 保留目录结构，否则用文件名
    const path = (f as any).webkitRelativePath || f.name
    formData.append('files', f, path)
  }
  importing.value = true
  try {
    const data: ImportResponse | null = await pageStore.importPages(formData)
    // 等待 Vue 完成响应式更新后再切换页面
    await nextTick()
    if (!data) {
      alert('导入失败：请确认后端已启动且你有该项目的写权限')
      return
    }
    const targetId = importTargetId.value
    if (targetId) {
      const msgs: string[] = []
      if (data.matched_target) {
        msgs.push(`✔ 已把同名文档「${data.matched_doc || ''}」的内容追加到当前页面`)
      } else if (data.created.length || data.skipped.length) {
        msgs.push('当前目录中未找到与当前页面同名的文档，当前页面保持为空')
      }
      if (data.container_note_id) {
        msgs.push('目录中其余内容已导入到“与目录同名”的子页面下')
      } else if (data.created.length && !data.matched_target) {
        msgs.push('目录内容已按结构建为当前页面的子页面')
      }
      if (data.skipped.length && data.skipped.length >= data.created.length) {
        msgs.push(`已有 ${data.skipped.length} 个文件被跳过（内容已存在）`)
      }
      if (msgs.length) alert(msgs.join('\n'))
      // 导入到已有笔记：刷新该笔记（顶层内容可能已追加）
      emit('select', targetId)
    } else if (data.root_note_id) {
      emit('select', data.root_note_id)
    } else if (data.skipped.length && !data.created.length) {
      alert('内容已存在，本次导入已跳过（如需重建请勾选覆盖重新导入）')
    }
  } finally {
    importing.value = false
  }
}

// 扁平化所有页面（用于移动到/嵌入到子菜单）
function flattenTree(nodes: PageTreeNodeType[]): PageTreeNodeType[] {
  const result: PageTreeNodeType[] = []
  function walk(list: PageTreeNodeType[]) {
    for (const n of list) {
      result.push(n)
      if (n.children) walk(n.children)
      if (n.linked_children) walk(n.linked_children)
    }
  }
  walk(nodes)
  return result
}
const flatPages = computed(() => flattenTree(pageStore.tree))

// 删除确认
const deleteTarget = ref<{ id: number; title: string } | null>(null)

async function confirmDelete() {
  if (!deleteTarget.value) return
  await pageStore.deletePage(deleteTarget.value.id)
  deleteTarget.value = null
}

async function handleAction(type: string, payload?: Record<string, unknown>) {
  if (!payload) return
  switch (type) {
    case 'rename':
      await pageStore.renamePage(payload.pageId as number, payload.title as string)
      break
    case 'move':
      await pageStore.movePage(payload.pageId as number, payload.parentId as number | null)
      // 移动到目标页面下时，在目标页面末尾添加该页面的引用链接
      if (payload.parentId) {
        await pageStore.addBlock(payload.parentId as number, 'page_link', {
          page_id: payload.pageId as number,
          title: payload.title as string || '',
        })
      }
      break
    case 'reorder':
      await pageStore.reorderPages(
        payload.pageId as number,
        payload.targetId as number,
        (payload.position as 'above' | 'below') || 'below',
      )
      break
    case 'embed':
      // 嵌入到：在该页面的 blocks 指定位置添加一个 page_link block
      {
        const position = (payload.position as string) || 'bottom'
        if (position === 'top') {
          await pageStore.insertBlockAt(payload.targetId as number, 0, 'page_link', {
            page_id: payload.pageId as number,
            title: '',
          })
        } else {
          await pageStore.addBlock(payload.targetId as number, 'page_link', {
            page_id: payload.pageId as number,
            title: '',
          })
        }
      }
      break
    case 'duplicate':
      await pageStore.duplicatePage(payload.pageId as number)
      break
    case 'delete':
      deleteTarget.value = { id: payload.pageId as number, title: payload.title as string }
      break
    case 'import':
      // 直接打开文件管理器导入
      triggerImport(payload.pageId as number)
      break
    case 'addSubPage':
      emit('create', payload.pageId as number)
      break
  }
}

let searchTimer: ReturnType<typeof setTimeout>
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => pageStore.searchPages(searchInput.value), 300)
}
</script>
