<template>
  <div
    class="block-item group relative flex gap-2"
    :class="{ 'bg-slate-50/50 -mx-4 px-4 rounded-lg': showHandle }"
    @mouseenter="showHandle = true"
    @mouseleave="showHandle = false"
    @contextmenu.prevent="onContextMenu"
  >
    <!-- ===== 左侧拖拽手柄 + 操作按钮 ===== -->
    <div class="relative shrink-0 pt-1.5" :class="{ 'opacity-0 group-hover:opacity-100': !blockMenuOpen }" :style="{ opacity: blockMenuOpen ? 1 : undefined }">
      <button
        class="w-6 h-6 flex items-center justify-center rounded text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors cursor-grab"
        title="拖拽移动 / 点击查看选项"
        @click.stop="toggleBlockMenu"
      >
        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M7 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7 14a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 14a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>
      </button>

      <!-- Block 操作下拉菜单 -->
      <Teleport to="body">
        <div v-if="blockMenuOpen" class="fixed inset-0 z-40" @click="blockMenuOpen = false" />
        <div v-if="blockMenuOpen" class="fixed z-50 w-52 bg-white rounded-xl shadow-lg border border-slate-200 py-1" :style="blockMenuStyle" @click.stop>
          <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">转换类型</div>
          <button v-for="bt in typeOptions" :key="bt.type" class="block-menu-item" @click="changeType(bt.type)">
            <span>{{ bt.icon }}</span><span>{{ bt.label }}</span>
          </button>
          <div class="my-0.5 border-t border-slate-100" />
          <button class="block-menu-item" @click="$emit('duplicate')">
            <span>📋</span><span>拷贝副本</span>
          </button>
          <button class="block-menu-item" @click="blockMenuOpen = false; showColorPicker = true">
            <span>🎨</span><span>修改颜色</span>
          </button>
          <div v-if="showColorPicker" class="px-3 py-1.5 flex gap-1 flex-wrap">
            <button v-for="c in colors" :key="c" class="w-5 h-5 rounded-full border border-slate-200" :style="{ background: c }" @click="setColor(c)" />
          </div>
          <button class="block-menu-item" @click="toggleCenter">
            <span>{{ isCentered ? '📐' : '📏' }}</span>
            <span>{{ isCentered ? '取消居中' : '文字居中' }}</span>
          </button>
          <div class="my-0.5 border-t border-slate-100" />
          <button class="block-menu-item" @click="$emit('moveUp')">
            <span>⬆️</span><span>上移</span>
          </button>
          <button class="block-menu-item" @click="$emit('moveDown')">
            <span>⬇️</span><span>下移</span>
          </button>
          <div class="my-0.5 border-t border-slate-100" />
          <button class="block-menu-item text-red-600 hover:bg-red-50" @click="$emit('delete')">
            <span>🗑️</span><span>删除</span>
          </button>
        </div>
      </Teleport>

      <!-- 右键菜单 -->
      <Teleport to="body">
        <div v-if="ctxMenuOpen" class="fixed inset-0 z-40" @click="ctxMenuOpen = false" />
        <div v-if="ctxMenuOpen" class="fixed z-50 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1" :style="ctxMenuStyle" @click.stop>
          <button class="block-menu-item" @click="quickConvert('heading', 1)"># 一级标题</button>
          <button class="block-menu-item" @click="quickConvert('heading', 2)">## 二级标题</button>
          <button class="block-menu-item" @click="quickConvert('heading', 3)">### 三级标题</button>
          <button class="block-menu-item" @click="quickConvert('list', false)">- 无序列表</button>
          <button class="block-menu-item" @click="quickConvert('list', true)">1. 有序列表</button>
          <button class="block-menu-item" @click="quickConvert('quote')">&gt; 引用</button>
          <div class="my-0.5 border-t border-slate-100" />
          <button class="block-menu-item" @click="$emit('duplicate'); ctxMenuOpen = false">📋 拷贝副本</button>
          <button class="block-menu-item" @click="$emit('delete'); ctxMenuOpen = false">🗑️ 删除</button>
        </div>
      </Teleport>
    </div>

    <!-- ===== Block 内容渲染 ===== -->
    <div class="flex-1 min-w-0" :style="blockStyle">
      <!-- 段落 -->
      <div v-if="block.type === 'paragraph'" class="py-1">
        <p
          v-if="!editing"
          class="text-slate-700 leading-relaxed whitespace-pre-wrap cursor-text min-h-[1.5em]"
          :class="{ 'text-slate-400': !text }"
          @click="startEdit"
        >{{ text || '输入内容...' }}</p>
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none text-slate-700 leading-relaxed"
          rows="1"
          @blur="saveEdit"
          @keydown.enter.exact="saveEdit"
          @keydown.escape="cancelEdit"
          @input="autoResize"
        />
      </div>

      <!-- 标题 -->
      <component
        v-else-if="block.type === 'heading'"
        :is="'h' + (level || 2)"
        class="font-bold text-slate-800 py-1 cursor-text group/heading"
        :class="headingClass"
        @click="startEdit"
      >
        <span v-if="!editing" :class="{ 'text-slate-300': !text }">{{ text || '标题 ' + level }}</span>
        <input
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full bg-transparent border-none outline-none font-bold"
          @blur="saveEdit"
          @keydown.enter="saveEdit"
          @keydown.escape="cancelEdit"
        />
      </component>

      <!-- 代码 -->
      <div v-else-if="block.type === 'code'" class="my-2">
        <div class="flex items-center justify-between mb-1">
          <span class="text-[10px] font-mono text-slate-400 uppercase">{{ language || 'text' }}</span>
          <button class="text-[10px] text-slate-400 hover:text-slate-600" @click="copyCode">复制</button>
        </div>
        <pre class="bg-slate-900 text-slate-100 rounded-xl p-4 text-sm overflow-x-auto font-mono"><code>{{ code }}</code></pre>
      </div>

      <!-- 引用 -->
      <blockquote
        v-else-if="block.type === 'quote'"
        class="border-l-4 border-brand-300 pl-4 py-1 text-slate-600 italic cursor-text"
        @click="startEdit"
      >
        <span v-if="!editing" :class="{ 'text-slate-300': !text }">{{ text || '引用内容' }}</span>
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none text-slate-600 italic"
          @blur="saveEdit"
          @keydown.enter.exact="saveEdit"
          @keydown.escape="cancelEdit"
        />
      </blockquote>

      <!-- 列表 -->
      <div v-else-if="block.type === 'list'" class="py-1">
        <p v-if="!editing" class="text-slate-700 leading-relaxed cursor-text" @click="startEdit">
          <span v-if="!listText" class="text-slate-400">列表项...</span>
          <span v-else>{{ isOrdered ? '1. ' : '• ' }}{{ listText }}</span>
        </p>
        <div v-else class="flex items-start gap-1">
          <span class="text-slate-400 pt-1.5">{{ isOrdered ? '1.' : '•' }}</span>
          <textarea
            ref="inputRef"
            v-model="editText"
            class="flex-1 resize-none bg-transparent border-none outline-none text-slate-700 leading-relaxed"
            rows="1"
            @blur="saveListEdit"
            @keydown.enter.exact="saveListEdit"
            @keydown.escape="cancelEdit"
          />
        </div>
      </div>

      <!-- 分割线 -->
      <hr v-else-if="block.type === 'divider'" class="my-4 border-slate-200" />

      <!-- 页面链接 -->
      <div
        v-else-if="block.type === 'page_link'"
        class="flex items-center gap-2 px-3 py-2 bg-brand-50 rounded-xl text-brand-700 cursor-pointer hover:bg-brand-100 transition-colors my-1"
        @click="navigateToPage"
      >
        <span>📎</span>
        <span class="font-medium">{{ linkTitle || '子页面' }}</span>
      </div>

      <!-- 图片 -->
      <div v-else-if="block.type === 'image'" class="my-2">
        <img v-if="block.content.url" :src="block.content.url" :alt="block.content.alt || ''" class="max-w-full rounded-xl" />
        <div v-else class="px-4 py-3 bg-slate-50 rounded-xl text-sm text-slate-400 text-center">🖼️ 点击添加图片URL</div>
      </div>

      <!-- 提示框 -->
      <div v-else-if="block.type === 'callout'" class="px-4 py-3 rounded-xl my-1" :class="calloutClass">
        <span v-if="!editing" class="cursor-text" @click="startEdit">{{ text || '提示内容' }}</span>
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none"
          @blur="saveEdit"
          @keydown.escape="cancelEdit"
        />
      </div>

      <!-- 默认/未知 -->
      <div v-else class="text-sm text-slate-400 py-1">[{{ block.type }}]</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import type { Block, PageTreeNode } from '@/types'

const props = defineProps<{
  block: Block
  allPages?: PageTreeNode[]
}>()

const emit = defineEmits<{
  save: [content: Record<string, unknown>]
  changeType: [newType: string]
  navigate: [pageId: number]
  delete: []
  duplicate: []
  moveUp: []
  moveDown: []
}>()

const showHandle = ref(false)
const editing = ref(false)
const editText = ref('')
const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

const text = computed(() => String(props.block.content.text || ''))
const code = computed(() => String(props.block.content.code || ''))
const language = computed(() => String(props.block.content.language || 'text'))
const level = computed(() => Number(props.block.content.level || 2))
const isOrdered = computed(() => Boolean(props.block.content.ordered))
const listText = computed(() => {
  const items = props.block.content.items as string[] | undefined
  return items?.join(', ') || String(props.block.content.text || '')
})
const linkTitle = computed(() => String(props.block.content.title || ''))
const pageId = computed(() => Number(props.block.content.page_id || 0))
const isCentered = computed(() => Boolean(props.block.content.centered))
const bgColor = computed(() => String(props.block.content.bg_color || ''))

const blockStyle = computed(() => {
  const style: Record<string, string> = {}
  if (isCentered.value) style.textAlign = 'center'
  if (bgColor.value) style.background = bgColor.value
  return style
})

const headingClass = computed(() => ({
  1: 'text-3xl',
  2: 'text-2xl',
  3: 'text-xl',
  4: 'text-lg',
  5: 'text-base',
  6: 'text-sm',
}[level.value] || 'text-2xl'))

const calloutClass = computed(() => {
  const t = String(props.block.content.type || 'info')
  const map: Record<string, string> = {
    info: 'bg-blue-50 text-blue-800',
    warning: 'bg-amber-50 text-amber-800',
    success: 'bg-green-50 text-green-800',
    error: 'bg-red-50 text-red-800',
  }
  return map[t] || map.info
})

// ===== Block 操作菜单 =====
const blockMenuOpen = ref(false)
const blockMenuStyle = ref<Record<string, string>>({})
const showColorPicker = ref(false)

const typeOptions = [
  { type: 'paragraph', label: '段落 ¶', icon: '¶' },
  { type: 'heading', label: '标题 H', icon: 'H' },
  { type: 'list', label: '列表 •', icon: '•' },
  { type: 'quote', label: '引用 ❝', icon: '❝' },
  { type: 'code', label: '代码 </>', icon: '</>' },
  { type: 'divider', label: '分割线 —', icon: '—' },
  { type: 'callout', label: '提示框 💡', icon: '💡' },
  { type: 'image', label: '图片 🖼️', icon: '🖼️' },
  { type: 'page_link', label: '页面链接 🔗', icon: '🔗' },
]

const colors = ['#fef3c7', '#dbeafe', '#dcfce7', '#fce7f3', '#f3e8ff', '#e0f2fe', '#fff7ed', '#f1f5f9']

function toggleBlockMenu(e: MouseEvent) {
  blockMenuOpen.value = !blockMenuOpen.value
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  blockMenuStyle.value = { top: `${rect.bottom + 4}px`, left: `${rect.left}px` }
  showColorPicker.value = false
}

function changeType(newType: string) {
  blockMenuOpen.value = false
  if (newType !== props.block.type) {
    emit('changeType', newType)
  }
}

function setColor(color: string) {
  showColorPicker.value = false
  blockMenuOpen.value = false
  emit('save', { ...props.block.content, bg_color: color === 'transparent' ? '' : color })
}

function toggleCenter() {
  blockMenuOpen.value = false
  emit('save', { ...props.block.content, centered: !isCentered.value })
}

// ===== 右键菜单 =====
const ctxMenuOpen = ref(false)
const ctxMenuStyle = ref<Record<string, string>>({})
function onContextMenu(e: MouseEvent) {
  ctxMenuOpen.value = true
  ctxMenuStyle.value = { top: `${e.clientY}px`, left: `${e.clientX}px` }
}
function quickConvert(type: string, extra?: number | boolean) {
  ctxMenuOpen.value = false
  const content: Record<string, unknown> = { ...props.block.content }
  if (type === 'heading') content.level = extra ?? 2
  else if (type === 'list') {
    content.ordered = extra ?? false
    content.items = text.value ? [text.value] : []
    delete content.text
  }
  emit('save', content)
  if (type !== props.block.type) {
    emit('changeType', type)
  }
}

// ===== 编辑逻辑 =====
async function startEdit(e?: MouseEvent) {
  if (['paragraph', 'heading', 'quote', 'callout', 'list'].includes(props.block.type)) {
    editing.value = true
    editText.value = text.value
    await nextTick()
    inputRef.value?.focus()
  }
}

function autoResize() {
  const el = inputRef.value
  if (el instanceof HTMLTextAreaElement) {
    el.style.height = 'auto'
    el.style.height = el.scrollHeight + 'px'
  }
}

function saveEdit() {
  if (!editing.value) return
  const newText = editText.value.trim()
  editing.value = false

  // Markdown 快捷转换
  const md = checkMarkdownShortcut(newText)
  if (md) {
    emit('save', { ...props.block.content, ...md.content })
    if (md.type && md.type !== props.block.type) {
      emit('changeType', md.type)
    }
    return
  }

  if (newText !== text.value) {
    emit('save', { ...props.block.content, text: newText })
  }
}

function saveListEdit() {
  if (!editing.value) return
  const newText = editText.value.trim()
  editing.value = false
  if (newText !== text.value) {
    emit('save', { ...props.block.content, items: [newText], text: newText })
  }
}

function cancelEdit() {
  editing.value = false
  editText.value = text.value
}

function checkMarkdownShortcut(input: string): { type?: string; content: Record<string, unknown> } | null {
  // # 标题
  const hMatch = input.match(/^(#{1,6})\s+(.+)/)
  if (hMatch) {
    return { type: 'heading', content: { level: hMatch[1].length, text: hMatch[2] } }
  }
  // - 列表
  if (/^[-*+]\s/.test(input)) {
    return { type: 'list', content: { ordered: false, items: [input.replace(/^[-*+]\s/, '')], text: input.replace(/^[-*+]\s/, '') } }
  }
  // 1. 有序列表
  if (/^\d+\.\s/.test(input)) {
    return { type: 'list', content: { ordered: true, items: [input.replace(/^\d+\.\s/, '')], text: input.replace(/^\d+\.\s/, '') } }
  }
  // > 引用
  if (input.startsWith('> ')) {
    return { type: 'quote', content: { text: input.slice(2) } }
  }
  // ``` 代码
  if (input.startsWith('```')) {
    return { type: 'code', content: { language: input.slice(3).trim() || 'text', code: '' } }
  }
  return null
}

function navigateToPage() {
  if (pageId.value) emit('navigate', pageId.value)
}

async function copyCode() {
  await navigator.clipboard.writeText(code.value)
}
</script>

<style scoped>
.block-menu-item {
  @apply w-full flex items-center gap-2 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors text-left;
}
</style>
