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
          {{ r.icon }} {{ r.title }}
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
        <button
          class="w-6 h-6 flex items-center justify-center rounded-lg hover:bg-brand-50 text-brand-600 transition-colors"
          title="新增页面"
          @click="$emit('create')"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
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
        :active-id="activeId"
        :all-pages="flatPages"
        @select="$emit('select', $event)"
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
      accept=".md,.html,.htm"
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
  </aside>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { usePageStore } from '@/stores/page'
import type { PageTreeNode as PageTreeNodeType } from '@/types'
import UserAvatar from '@/components/common/UserAvatar.vue'
import PageTreeNode from './PageTreeNode.vue'

defineProps<{ activeId?: number | null }>()
const emit = defineEmits<{ select: [id: number]; create: []; createSubPage: [parentId: number] }>()

const auth = useAuthStore()
const pageStore = usePageStore()
const router = useRouter()
const searchInput = ref('')

// 文件导入
const dirInput = ref<HTMLInputElement>()
const fileInput = ref<HTMLInputElement>()
const importDialogOpen = ref(false)
const importParentId = ref<number>(0)

function triggerImport(pageId: number) {
  importParentId.value = pageId
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
  if (importParentId.value) {
    formData.append('parent_id', String(importParentId.value))
  }
  for (let i = 0; i < fileList.length; i++) {
    const f = fileList[i]
    // webkitRelativePath 保留目录结构，否则用文件名
    const path = (f as any).webkitRelativePath || f.name
    formData.append('files', f, path)
  }
  await pageStore.importPages(formData)
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
      break
    case 'embed':
      // 嵌入到：在该页面的 blocks 末尾添加一个 page_link block
      await pageStore.addBlock(payload.targetId as number, 'page_link', {
        page_id: payload.pageId as number,
        title: '',
      })
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
      emit('createSubPage', payload.pageId as number)
      break
  }
}

let searchTimer: ReturnType<typeof setTimeout>
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => pageStore.searchPages(searchInput.value), 300)
}
</script>
