<template>
  <div class="flex-1 flex flex-col h-full bg-white">
    <!-- ===== 头部 ===== -->
    <header class="h-14 border-b border-slate-100 flex items-center justify-between px-4 shrink-0 gap-3">
      <!-- 左侧 -->
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <button
          class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors shrink-0"
          title="收起侧边栏"
          @click="$emit('toggleSidebar')"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>
        </button>
        <span v-if="page" class="text-lg shrink-0">{{ page.icon || '📄' }}</span>
        <input
          v-if="page"
          :value="page.title"
          class="text-lg font-semibold text-slate-800 bg-transparent border-none outline-none min-w-0 flex-1"
          placeholder="无标题"
          @change="onTitleChange"
        />
        <span v-else class="text-lg font-semibold text-slate-400">无标题</span>
      </div>

      <!-- 右侧工具 -->
      <div class="flex items-center gap-1 shrink-0">
        <!-- 星标置顶 -->
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg transition-colors"
          :class="page.is_pinned ? 'text-amber-500 bg-amber-50 hover:bg-amber-100' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600'"
          title="星标置顶"
          @click="togglePin"
        >
          <svg class="w-4 h-4" :fill="page.is_pinned ? 'currentColor' : 'none'" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" /></svg>
        </button>
        <!-- 页面关系图 -->
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          title="页面关系图"
          @click="$router.push('/graph')"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>
        </button>
        <!-- 协作（预留） -->
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-300 cursor-not-allowed"
          title="页面协作（即将推出）"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" /></svg>
        </button>
        <!-- 编辑历史（预留） -->
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-300 cursor-not-allowed"
          title="查看编辑记录（即将推出）"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        </button>
        <!-- "..." 页面更多选项 -->
        <div v-if="page" class="relative" ref="pageMenuRef">
          <button
            class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            @click.stop="showPageMenu = !showPageMenu"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zM12 10a2 2 0 11-4 0 2 2 0 014 0zM16 12a2 2 0 100-4 2 2 0 000 4z" /></svg>
          </button>
          <Teleport to="body">
            <div v-if="showPageMenu" class="fixed inset-0 z-40" @click="showPageMenu = false" />
            <div v-if="showPageMenu" class="fixed z-50 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1" :style="pageMenuStyle" @click.stop>
              <button class="page-menu-item" @click="handleImportHtml">📥 导入 HTML 文件</button>
              <button class="page-menu-item" @click="handleImportMd">📝 导入 Markdown 文件</button>
              <div class="my-1 border-t border-slate-100" />
              <button class="page-menu-item" @click="showPageMenu = false; $emit('pageAction', 'rename')">✏️ 重命名</button>
              <button class="page-menu-item" @click="showPageMenu = false; $emit('pageAction', 'duplicate')">📋 拷贝副本</button>
              <button class="page-menu-item text-red-600 hover:bg-red-50" @click="showPageMenu = false; $emit('pageAction', 'delete')">🗑️ 删除</button>
            </div>
          </Teleport>
        </div>
      </div>
    </header>

    <!-- ===== 内容区 ===== -->
    <div class="flex-1 overflow-y-auto">
      <!-- 空状态 -->
      <div v-if="!page" class="flex items-center justify-center h-full text-slate-400">
        <div class="text-center">
          <div class="text-5xl mb-4">📝</div>
          <p class="text-lg font-medium text-slate-500">选择或创建一个页面</p>
          <p class="text-sm mt-1">从左侧侧边栏开始你的知识之旅</p>
        </div>
      </div>

      <!-- 加载中 -->
      <div v-else-if="pageStore.loading" class="flex items-center justify-center h-full">
        <div class="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>

      <!-- Block 内容 -->
      <div v-else class="max-w-3xl mx-auto px-8 py-8">
        <BlockRenderer
          v-for="(block, idx) in page.blocks"
          :key="block.id"
          :block="block"
          :all-pages="flatPages"
          @save="(c) => onBlockSave(block.id, c)"
          @change-type="(t) => onChangeBlockType(block.id, t)"
          @navigate="(id) => $emit('navigate', id)"
          @delete="onBlockDelete(block.id)"
          @duplicate="onBlockDuplicate(block.id)"
          @move-up="onBlockMove(idx, -1)"
          @move-down="onBlockMove(idx, 1)"
        />

        <!-- 添加 Block 按钮 -->
        <div class="relative mt-3" ref="addBlockRef">
          <button
            v-if="page"
            class="w-full py-3 text-sm text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-xl transition-all border border-dashed border-slate-200 flex items-center justify-center gap-2"
            @click="showAddBlock = !showAddBlock"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
            添加内容
          </button>
          <Teleport to="body">
            <div v-if="showAddBlock" class="fixed inset-0 z-40" @click="showAddBlock = false" />
            <div v-if="showAddBlock" class="fixed z-50 w-64 bg-white rounded-xl shadow-lg border border-slate-200 py-1" :style="addBlockStyle" @click.stop>
              <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">基础块</div>
              <button v-for="bt in baseBlocks" :key="bt.type" class="block-menu-item" @click="addBlock(bt.type, bt.default)">
                <span class="w-8 h-8 flex items-center justify-center bg-slate-50 rounded-lg text-lg">{{ bt.icon }}</span>
                <div class="flex-1 text-left">
                  <div class="text-sm font-medium">{{ bt.label }}</div>
                  <div class="text-[10px] text-slate-400">{{ bt.shortcut }}</div>
                </div>
              </button>
              <div class="my-1 border-t border-slate-100" />
              <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">媒体 &amp; 嵌入</div>
              <button v-for="bt in mediaBlocks" :key="bt.type" class="block-menu-item" @click="addBlock(bt.type, bt.default)">
                <span class="w-8 h-8 flex items-center justify-center bg-slate-50 rounded-lg text-lg">{{ bt.icon }}</span>
                <div class="flex-1 text-left">
                  <div class="text-sm font-medium">{{ bt.label }}</div>
                  <div class="text-[10px] text-slate-400">{{ bt.shortcut }}</div>
                </div>
              </button>
            </div>
          </Teleport>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { usePageStore } from '@/stores/page'
import { pagesApi } from '@/api/pages'
import type { PageTreeNode } from '@/types'
import BlockRenderer from './BlockRenderer.vue'

const emit = defineEmits<{ navigate: [id: number]; toggleSidebar: []; pageAction: [type: string] }>()

const pageStore = usePageStore()
const router = useRouter()
const page = computed(() => pageStore.currentPage)

// 扁平化页面列表
function flattenTree(nodes: PageTreeNode[]): PageTreeNode[] {
  const result: PageTreeNode[] = []
  function walk(list: PageTreeNode[]) {
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

// ===== 头部 =====
const showPageMenu = ref(false)
const pageMenuRef = ref<HTMLElement>()
const pageMenuStyle = ref<Record<string, string>>({})
function togglePageMenu(e: MouseEvent) {
  showPageMenu.value = !showPageMenu.value
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  pageMenuStyle.value = { top: `${rect.bottom + 4}px`, right: `${window.innerWidth - rect.right}px` }
}

async function togglePin() {
  if (!page.value) return
  await pageStore.updatePage(page.value.id, { is_pinned: !page.value.is_pinned })
}

async function onTitleChange(e: Event) {
  if (!page.value) return
  const title = (e.target as HTMLInputElement).value || '无标题'
  await pagesApi.update(page.value.id, { title })
  page.value.title = title
  await pageStore.fetchTree()
}

// 导入文件
const fileInput = ref<HTMLInputElement>()
const importFormat = ref<'html' | 'md'>('md')
function handleImportHtml() { showPageMenu.value = false; importFormat.value = 'html'; fileInput.value?.click() }
function handleImportMd() { showPageMenu.value = false; importFormat.value = 'md'; fileInput.value?.click() }
async function onFileChange(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file || !page.value) return
  const text = await file.text()
  await pageStore.importToPage(page.value.id, text, importFormat.value)
}

// ===== Block 添加 =====
const showAddBlock = ref(false)
const addBlockRef = ref<HTMLElement>()
const addBlockStyle = ref<Record<string, string>>({})

const baseBlocks = [
  { type: 'paragraph', label: '段落', icon: '¶', shortcut: '输入文本', default: { text: '' } },
  { type: 'heading', label: '一级标题', icon: 'H1', shortcut: '# 空格', default: { level: 1, text: '' } },
  { type: 'heading', label: '二级标题', icon: 'H2', shortcut: '## 空格', default: { level: 2, text: '' } },
  { type: 'heading', label: '三级标题', icon: 'H3', shortcut: '### 空格', default: { level: 3, text: '' } },
  { type: 'list', label: '无序列表', icon: '•', shortcut: '- 空格', default: { ordered: false, items: [] } },
  { type: 'list', label: '有序列表', icon: '1.', shortcut: '1. 空格', default: { ordered: true, items: [] } },
  { type: 'quote', label: '引用', icon: '❝', shortcut: '> 空格', default: { text: '' } },
  { type: 'divider', label: '分割线', icon: '—', shortcut: '---', default: {} },
  { type: 'code', label: '代码块', icon: '</>', shortcut: '``` 语言', default: { language: 'python', code: '' } },
  { type: 'callout', label: '提示框', icon: '💡', shortcut: '', default: { type: 'info', text: '提示内容' } },
]
const mediaBlocks = [
  { type: 'page_link', label: '页面链接', icon: '🔗', shortcut: '', default: { page_id: 0, title: '' } },
  { type: 'image', label: '图片', icon: '🖼️', shortcut: '', default: { url: '', alt: '' } },
]

function toggleAddBlock(e: MouseEvent) {
  showAddBlock.value = !showAddBlock.value
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  addBlockStyle.value = { top: `${rect.top - 200}px`, left: `${rect.left}px` }
}

watch(showAddBlock, (v) => {
  if (v && addBlockRef.value) {
    const rect = addBlockRef.value.getBoundingClientRect()
    addBlockStyle.value = { top: `${Math.max(rect.top - 300, 60)}px`, left: `${rect.left}px` }
  }
})

async function addBlock(type: string, content: Record<string, unknown>) {
  if (!page.value) return
  showAddBlock.value = false
  await pageStore.addBlock(page.value.id, type, content)
}

async function onBlockSave(blockId: number, content: Record<string, unknown>) {
  await pageStore.updateBlock(blockId, { content })
}
async function onChangeBlockType(blockId: number, newType: string) {
  await pageStore.updateBlock(blockId, { type: newType })
}
async function onBlockDelete(blockId: number) {
  await pageStore.deleteBlock(blockId)
}
async function onBlockDuplicate(blockId: number) {
  await pageStore.duplicateBlock(blockId)
}
async function onBlockMove(idx: number, delta: number) {
  if (!page.value) return
  const newIdx = idx + delta
  if (newIdx < 0 || newIdx >= page.value.blocks.length) return
  const ids = page.value.blocks.map(b => b.id)
  const temp = ids[idx]; ids[idx] = ids[newIdx]; ids[newIdx] = temp
  await pageStore.reorderBlocks(page.value.id, ids)
}
</script>

<style scoped>
.page-menu-item {
  @apply w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors text-left;
}
.block-menu-item {
  @apply w-full flex items-center gap-3 px-3 py-2 hover:bg-slate-50 transition-colors text-left;
}
</style>
