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

        <!-- 面包屑导航 -->
        <nav v-if="page" class="flex items-center gap-1 min-w-0 text-sm">
          <template v-for="(crumb, i) in breadcrumbs" :key="crumb.id">
            <span v-if="i > 0" class="text-slate-300 shrink-0">›</span>
            <button
              class="truncate max-w-[160px] hover:text-brand-600 transition-colors shrink-0"
              :class="i === breadcrumbs.length - 1 ? 'font-semibold text-slate-800' : 'text-slate-500'"
              :title="crumb.title"
              @click="onNavigateBreadcrumb(crumb)"
            >
              {{ crumb.title }}
            </button>
          </template>
        </nav>
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
        <!-- "..." 页面设置 -->
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          :class="{ 'bg-slate-100 text-slate-600': showSettingsPanel }"
          title="页面设置"
          @click="showSettingsPanel = !showSettingsPanel"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zM12 10a2 2 0 11-4 0 2 2 0 014 0zM16 12a2 2 0 100-4 2 2 0 000 4z" /></svg>
        </button>
      </div>
    </header>

    <!-- ===== 内容区 ===== -->
    <div class="flex-1 flex overflow-hidden transition-all duration-300" :style="contentAreaStyle">
      <!-- 主内容区 -->
      <div class="flex-1 overflow-y-auto" ref="contentAreaRef">
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
        <div v-else :class="['mx-auto px-8 py-8', pageSettings.adaptiveWidth ? 'max-w-full' : 'max-w-3xl', pageSettings.smallFont ? 'text-sm' : '']">
          <BlockRenderer
            v-for="(block, idx) in page.blocks"
            :key="block.id"
            :block="block"
            :all-pages="flatPages"
            :settings="pageSettings"
            :heading-number="headingNumbers.get(block.id) || ''"
            @save="(c) => onBlockSave(block.id, c)"
            @change-type="(t) => onChangeBlockType(block.id, t)"
            @navigate="(id) => $emit('navigate', id)"
            @delete="onBlockDelete(block.id)"
            @duplicate="onBlockDuplicate(block.id)"
            @move-up="onBlockMove(idx, -1)"
            @move-down="onBlockMove(idx, 1)"
            @create-below="onCreateBelow(idx)"
            @insert-above="onInsertAt(idx)"
            @insert-below="onInsertAt(idx + 1)"
            @move-to="(targetIdx) => onMoveTo(idx, targetIdx)"
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

      <!-- ===== 标题目录侧栏（行内右侧，可拖拽调整宽度） ===== -->
      <aside
        v-if="pageSettings.showToc && page && headingTree.length > 0"
        class="shrink-0 overflow-y-auto border-l border-slate-100 bg-white relative"
        :style="{ width: tocWidth + 'px' }"
      >
        <!-- 拖拽调整宽度手柄 -->
        <div
          class="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-brand-400/30 transition-colors group/resize z-10"
          @mousedown="onTocResizeStart"
        >
          <div class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-8 bg-slate-200 group-hover/resize:bg-brand-400 transition-colors rounded" />
        </div>
        <div class="px-3 py-4">
          <h4 class="text-xs font-semibold text-slate-400 mb-3 px-1">目录</h4>
          <nav class="space-y-0">
            <div v-for="(node, idx) in visibleHeadings" :key="node.blockId">
              <div
                class="flex items-center group/toc rounded hover:bg-slate-50 transition-colors cursor-pointer"
                :style="{ paddingLeft: `${(node.level - minHeadingLevel) * 12 + 4}px` }"
                @click="scrollToBlock(node.blockId)"
              >
                <!-- 折叠/展开按钮 -->
                <button
                  v-if="node.children.length > 0"
                  class="w-5 h-5 shrink-0 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors rounded"
                  @click.stop="toggleCollapse(node.blockId)"
                >
                  <svg class="w-3 h-3 transition-transform" :class="collapsedMap[node.blockId] ? '' : 'rotate-90'" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7" /></svg>
                </button>
                <!-- 占位（无子标题时对齐） -->
                <span v-else class="w-5 h-5 shrink-0" />
                <!-- 标题文字 -->
                <span
                  class="text-sm py-1 truncate flex-1"
                  :class="node.level === minHeadingLevel ? 'font-semibold text-slate-700' : 'text-slate-500 hover:text-slate-700'"
                  :title="node.text"
                >
                  <span v-if="pageSettings.autoNumbering" class="text-slate-400 mr-1 font-mono text-[0.8em]">{{ node.number }}</span>
                  {{ node.text }}
                </span>
              </div>
            </div>
          </nav>
        </div>
      </aside>
    </div>

    <!-- ===== 右侧设置面板 ===== -->
    <PageSettingsPanel
      :visible="showSettingsPanel"
      :page="page"
      @close="showSettingsPanel = false"
      @update-settings="onSettingsUpdate"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { usePageStore } from '@/stores/page'
import { pagesApi } from '@/api/pages'
import type { PageTreeNode } from '@/types'
import BlockRenderer from './BlockRenderer.vue'
import PageSettingsPanel from './PageSettingsPanel.vue'
import type { PageSettings } from './PageSettingsPanel.vue'

const emit = defineEmits<{ navigate: [id: number]; toggleSidebar: []; pageAction: [type: string] }>()

const pageStore = usePageStore()
const router = useRouter()
const page = computed(() => pageStore.currentPage)

// 面包屑
const breadcrumbs = computed(() => {
  if (!page.value) return []
  return pageStore.getBreadcrumb(page.value.id)
})

function onNavigateBreadcrumb(crumb: { id: number; slug: string }) {
  emit('navigate', crumb.id)
}

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

// ===== 标题目录：树结构与折叠 =====
interface TocNode {
  blockId: number
  level: number
  text: string
  number: string
  children: TocNode[]
}

// 标题树
const headingTree = computed<TocNode[]>(() => {
  if (!page.value?.blocks) return []
  const root: TocNode[] = []
  const stack: TocNode[] = []
  const counters = [0, 0, 0, 0, 0, 0]

  for (const block of page.value.blocks) {
    if (block.type !== 'heading') continue
    const level = Number((block.content as Record<string, unknown>).level) || 1
    if (level < 1 || level > 6) continue
    const text = String((block.content as Record<string, unknown>).text || '').trim()
    if (!text) continue

    // 编号
    counters[level - 1]++
    for (let l = level; l < 6; l++) counters[l] = 0
    const number = counters.slice(0, level).join('.')

    const node: TocNode = { blockId: block.id, level, text, number, children: [] }

    // 找到父节点：栈中层级小于当前层级的最近节点
    while (stack.length > 0 && stack[stack.length - 1].level >= level) {
      stack.pop()
    }
    if (stack.length > 0) {
      stack[stack.length - 1].children.push(node)
    } else {
      root.push(node)
    }
    stack.push(node)
  }
  return root
})

// 页面中最低的标题层级（用于计算缩进）
const minHeadingLevel = computed(() => {
  if (headingTree.value.length === 0) return 1
  let min = 6
  for (const node of headingTree.value) {
    min = Math.min(min, node.level)
  }
  return min
})

// 折叠状态（key: blockId）
const collapsedMap = ref<Record<number, boolean>>({})

// 初始化折叠状态：默认只展开前两级（相对层级）
watch(headingTree, (tree) => {
  const map: Record<number, boolean> = {}
  const initCollapse = (nodes: TocNode[], depthFromMin: number) => {
    for (const node of nodes) {
      // depthFromMin >= 2 即第三级及以上默认折叠
      map[node.blockId] = depthFromMin >= 2
      initCollapse(node.children, depthFromMin + 1)
    }
  }
  initCollapse(tree, 0)
  collapsedMap.value = map
}, { immediate: true })

// 可见标题（扁平化，尊重折叠状态）
const visibleHeadings = computed<TocNode[]>(() => {
  const result: TocNode[] = []
  const walk = (nodes: TocNode[]) => {
    for (const node of nodes) {
      result.push(node)
      if (!collapsedMap.value[node.blockId]) {
        walk(node.children)
      }
    }
  }
  walk(headingTree.value)
  return result
})

function toggleCollapse(blockId: number) {
  collapsedMap.value = {
    ...collapsedMap.value,
    [blockId]: !collapsedMap.value[blockId],
  }
}

// ===== 标题自动编号：计算每个 heading block 的编号 =====
const headingNumbers = computed(() => {
  const map = new Map<number, string>()
  if (!page.value?.blocks) return map
  const counters = [0, 0, 0, 0, 0, 0]
  for (const block of page.value.blocks) {
    if (block.type !== 'heading') continue
    const level = Number((block.content as Record<string, unknown>).level) || 1
    if (level < 1 || level > 6) continue
    counters[level - 1]++
    for (let l = level; l < 6; l++) counters[l] = 0
    map.set(block.id, counters.slice(0, level).join('.'))
  }
  return map
})

// ===== 页面设置面板 =====
const showSettingsPanel = ref(false)

// 主内容区样式：当右侧设置面板打开时，为 TOC 预留空间
const contentAreaStyle = computed(() => {
  if (showSettingsPanel.value) {
    return { marginRight: '320px' }
  }
  return {}
})

// TOC 宽度拖拽
const tocWidth = ref(224)
const MIN_TOC_WIDTH = 150
const MAX_TOC_WIDTH_RATIO = 0.4

function onTocResizeStart(e: MouseEvent) {
  const startX = e.clientX
  const startWidth = tocWidth.value
  const contentArea = contentAreaRef.value
  const maxWidth = contentArea ? contentArea.clientWidth * MAX_TOC_WIDTH_RATIO : 500

  function onMove(ev: MouseEvent) {
    const delta = startX - ev.clientX
    tocWidth.value = Math.max(MIN_TOC_WIDTH, Math.min(maxWidth, startWidth + delta))
  }
  function onUp() {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}
const pageSettings = ref<PageSettings>({
  adaptiveWidth: false,
  smallFont: false,
  showToc: false,
  autoNumbering: false,
})
const contentAreaRef = ref<HTMLElement>()

// 从 localStorage 加载设置
function loadPageSettings() {
  try {
    const raw = localStorage.getItem('page-settings')
    if (raw) {
      pageSettings.value = { ...pageSettings.value, ...JSON.parse(raw) }
    }
  } catch { /* ignore */ }
}
loadPageSettings()

function onSettingsUpdate(settings: PageSettings) {
  pageSettings.value = { ...settings }
}

/** 滚动到指定 block */
function scrollToBlock(blockId: number) {
  const container = contentAreaRef.value
  if (!container) return
  // 通过 data-block-id 属性查找对应的 DOM 元素
  const el = container.querySelector(`[data-block-id="${blockId}"]`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
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

// ===== Block 添加 =====
const showAddBlock = ref(false)
const addBlockRef = ref<HTMLElement>()
const addBlockStyle = ref<Record<string, string>>({})

const baseBlocks = [
  { type: 'paragraph', label: '段落', icon: '¶', shortcut: '输入文本', default: { text: '' } },
  { type: 'heading', label: '一级标题', icon: 'H1', shortcut: '# 空格 / Ctrl+1', default: { level: 1, text: '' } },
  { type: 'heading', label: '二级标题', icon: 'H2', shortcut: '## 空格 / Ctrl+2', default: { level: 2, text: '' } },
  { type: 'heading', label: '三级标题', icon: 'H3', shortcut: '### 空格 / Ctrl+3', default: { level: 3, text: '' } },
  { type: 'list', label: '无序列表', icon: '•', shortcut: '- 空格', default: { ordered: false, items: [] } },
  { type: 'list', label: '有序列表', icon: '1.', shortcut: '1. 空格', default: { ordered: true, items: [] } },
  { type: 'list', label: '任务列表', icon: '☑', shortcut: '- [ ] 空格', default: { ordered: false, task: true, items: [] } },
  { type: 'quote', label: '引用', icon: '❝', shortcut: '> 空格', default: { text: '' } },
  { type: 'divider', label: '分割线', icon: '—', shortcut: '---', default: {} },
  { type: 'table', label: '表格', icon: '▦', shortcut: '| 列1 | 列2 |', default: { headers: ['列1', '列2'], rows: [] } },
  { type: 'code', label: '代码块', icon: '</>', shortcut: '``` 语言 / Ctrl+Shift+K', default: { language: 'python', code: '' } },
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
  // 如果是 H1 块，同步更新页面标题
  syncTitleFromH1(blockId)
}

function syncTitleFromH1(blockId: number) {
  if (!page.value) return
  const block = page.value.blocks.find(b => b.id === blockId)
  if (!block || block.type !== 'heading') return
  const level = (block.content as Record<string, unknown>).level
  if (level !== 1) return
  const h1Text = String((block.content as Record<string, unknown>).text || '').trim()
  if (h1Text && h1Text !== page.value.title) {
    pagesApi.update(page.value.id, { title: h1Text })
    page.value.title = h1Text
    pageStore.fetchTree()
  }
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

/** Enter 键：在当前 Block 下方插入新段落并聚焦 */
async function onCreateBelow(idx: number) {
  if (!page.value) return
  // 在当前 block 之后插入一个新的空 paragraph block
  const newBlock = await pageStore.insertBlockAt(page.value.id, idx + 1, 'paragraph', { text: '' })
  // 同步排序到后端
  const ids = page.value.blocks.map(b => b.id)
  await pageStore.reorderBlocks(page.value.id, ids)
  // 等待 DOM 更新后聚焦到新 block
  await nextTick()
  const el = contentAreaRef.value?.querySelector(`[data-block-id="${newBlock.id}"] textarea, [data-block-id="${newBlock.id}"] input`)
  if (el instanceof HTMLElement) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.focus()
  }
}

/** 悬停 + 按钮：在指定位置插入新段落 */
async function onInsertAt(idx: number) {
  if (!page.value) return
  const insertIdx = Math.max(0, Math.min(idx, page.value.blocks.length))
  const newBlock = await pageStore.insertBlockAt(page.value.id, insertIdx, 'paragraph', { text: '' })
  const ids = page.value.blocks.map(b => b.id)
  await pageStore.reorderBlocks(page.value.id, ids)
  await nextTick()
  const el = contentAreaRef.value?.querySelector(`[data-block-id="${newBlock.id}"] textarea, [data-block-id="${newBlock.id}"] input`)
  if (el instanceof HTMLElement) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.focus()
  }
}

/** 拖拽排序：将当前 block 移动到 targetIndex */
async function onMoveTo(fromIdx: number, toIdx: number) {
  if (!page.value || fromIdx === toIdx) return
  const ids = page.value.blocks.map(b => b.id)
  const moved = ids.splice(fromIdx, 1)[0]
  const adjustedTo = fromIdx < toIdx ? toIdx - 1 : toIdx
  ids.splice(adjustedTo, 0, moved)
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
