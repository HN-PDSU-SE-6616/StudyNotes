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
        <div v-if="ctxMenuOpen" class="fixed z-50 w-52 bg-white rounded-xl shadow-lg border border-slate-200 py-1" :style="ctxMenuStyle" @click.stop>
          <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">转换为</div>
          <button class="block-menu-item" @click="quickConvert('heading', 1)"><span class="text-xs font-mono text-slate-400 w-5">H1</span> # 一级标题</button>
          <button class="block-menu-item" @click="quickConvert('heading', 2)"><span class="text-xs font-mono text-slate-400 w-5">H2</span> ## 二级标题</button>
          <button class="block-menu-item" @click="quickConvert('heading', 3)"><span class="text-xs font-mono text-slate-400 w-5">H3</span> ### 三级标题</button>
          <button class="block-menu-item" @click="quickConvert('heading', 4)"><span class="text-xs font-mono text-slate-400 w-5">H4</span> #### 四级标题</button>
          <button class="block-menu-item" @click="quickConvert('list', false)"><span class="w-5">•</span> 无序列表</button>
          <button class="block-menu-item" @click="quickConvert('list', true)"><span class="w-5">1.</span> 有序列表</button>
          <button class="block-menu-item" @click="quickConvert('quote')"><span class="w-5">❝</span> 引用</button>
          <button class="block-menu-item" @click="quickConvert('code')"><span class="w-5">&lt;/&gt;</span> 代码块</button>
          <div class="my-0.5 border-t border-slate-100" />
          <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">操作</div>
          <button class="block-menu-item" @click="$emit('duplicate'); ctxMenuOpen = false"><span class="w-5">📋</span> 拷贝副本</button>
          <button class="block-menu-item" @click="$emit('delete'); ctxMenuOpen = false"><span class="w-5">🗑️</span> 删除</button>
        </div>
      </Teleport>
    </div>

    <!-- ===== Block 内容渲染 ===== -->
    <div class="flex-1 min-w-0" :style="blockStyle">
      <!-- 段落 -->
      <div v-if="block.type === 'paragraph'" class="py-1">
        <p
          v-if="!editing"
          class="text-slate-700 leading-relaxed cursor-text min-h-[1.5em]"
          :class="{ [placeholderClass]: !text }"
          @click="startEdit"
          v-html="formattedText || '输入内容...'"
        />
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none text-slate-700 leading-relaxed"
          rows="1"
          @blur="saveEdit"
          @keydown.enter.exact="saveEdit"
          @keydown.escape="cancelEdit"
          @keydown="onEditKeydown"
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
        <span v-if="!editing" :class="{ [placeholderClass]: !text }" v-html="formattedText || '标题 ' + level" />
        <input
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full bg-transparent border-none outline-none font-bold"
          @blur="saveEdit"
          @keydown.enter="saveEdit"
          @keydown.escape="cancelEdit"
          @keydown="onEditKeydown"
        />
      </component>

      <!-- 代码 -->
      <div v-else-if="block.type === 'code'" class="my-2">
        <div v-if="!editing" class="cursor-pointer" @click="startEdit">
          <div class="flex items-center justify-between mb-1">
            <span class="text-[10px] font-mono text-slate-400 uppercase">{{ language || 'text' }}</span>
            <button class="text-[10px] text-slate-400 hover:text-slate-600" @click.stop="copyCode">复制</button>
          </div>
          <pre class="bg-slate-900 text-slate-100 rounded-xl p-4 text-sm overflow-x-auto font-mono min-h-[3em]"><code>{{ code || '点击编辑代码...' }}</code></pre>
        </div>
        <div v-else class="bg-slate-900 rounded-xl overflow-hidden">
          <div class="flex items-center gap-2 px-3 py-2 border-b border-slate-700">
            <input
              v-model="editLanguage"
              class="bg-transparent text-[10px] font-mono text-slate-400 uppercase outline-none w-20"
              placeholder="text"
              @keydown.escape="cancelEdit"
            />
            <div class="flex-1" />
            <button class="text-[10px] text-slate-400 hover:text-slate-200" @click="copyCode">复制</button>
          </div>
          <textarea
            ref="inputRef"
            v-model="editText"
            class="w-full resize-none bg-transparent text-slate-100 p-4 text-sm font-mono outline-none min-h-[120px]"
            placeholder="输入代码..."
            @keydown.escape="cancelEdit"
            @blur="saveCodeEdit"
          />
        </div>
      </div>

      <!-- 引用 -->
      <blockquote
        v-else-if="block.type === 'quote'"
        class="border-l-4 border-brand-300 pl-4 py-1 text-slate-600 italic cursor-text"
        @click="startEdit"
      >
        <span v-if="!editing" :class="{ [placeholderClass]: !text }" v-html="formattedText || '引用内容'" />
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none text-slate-600 italic"
          @blur="saveEdit"
          @keydown.enter.exact="saveEdit"
          @keydown.escape="cancelEdit"
          @keydown="onEditKeydown"
        />
      </blockquote>

      <!-- 列表 / 任务列表 -->
      <div v-else-if="block.type === 'list'" class="py-1">
        <!-- 任务列表 -->
        <div v-if="isTask && !editing" class="space-y-0.5">
          <div
            v-for="(item, i) in listItems"
            :key="i"
            class="flex items-start gap-2 py-0.5 group cursor-pointer"
            @click="toggleTaskItem(i)"
          >
            <span class="w-4 h-4 mt-0.5 rounded border-2 shrink-0 flex items-center justify-center transition-colors"
              :class="item.checked ? 'bg-brand-500 border-brand-500 text-white' : 'border-slate-300 hover:border-brand-400'"
            >
              <svg v-if="item.checked" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
            </span>
            <span class="text-slate-700 leading-relaxed" :class="{ 'line-through text-slate-400': item.checked }" v-html="renderInlineMarkdown(item.text) || '任务项'" />
          </div>
        </div>
        <!-- 普通列表显示 -->
        <div v-else-if="!editing" class="cursor-text" @click="startEdit">
          <p v-if="!listText" class="text-slate-400">{{ isOrdered ? '1. 列表项...' : '• 列表项...' }}</p>
          <p v-else class="text-slate-700 leading-relaxed">
            <span v-if="!isTask" class="text-slate-400 mr-1">{{ isOrdered ? '1. ' : '• ' }}</span>
            <span v-html="formattedListText" />
          </p>
        </div>
        <!-- 编辑模式 -->
        <div v-else class="flex items-start gap-1">
          <span v-if="isTask" class="w-4 h-4 mt-1.5 rounded border-2 border-slate-300 shrink-0" />
          <span v-else class="text-slate-400 pt-1.5">{{ isOrdered ? '1.' : '•' }}</span>
          <textarea
            ref="inputRef"
            v-model="editText"
            class="flex-1 resize-none bg-transparent border-none outline-none text-slate-700 leading-relaxed"
            rows="1"
            @blur="saveListEdit"
            @keydown.enter.exact="saveListEdit"
            @keydown.escape="cancelEdit"
            @keydown="onEditKeydown"
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
        <img v-if="imageUrl" :src="imageUrl" :alt="imageAlt" class="max-w-full rounded-xl cursor-pointer" @click="startEdit" />
        <div
          v-else-if="!editing"
          class="px-4 py-3 bg-slate-50 rounded-xl text-sm text-slate-400 text-center cursor-pointer hover:bg-slate-100"
          @click="startEdit"
        >🖼️ 点击添加图片URL</div>
        <div v-else class="flex gap-2">
          <input
            ref="inputRef"
            v-model="editText"
            class="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:border-brand-400"
            placeholder="输入图片URL..."
            @keydown.enter="saveEdit"
            @keydown.escape="cancelEdit"
            @blur="saveEdit"
          />
        </div>
      </div>

      <!-- 提示框 -->
      <div v-else-if="block.type === 'callout'" class="px-4 py-3 rounded-xl my-1" :class="calloutClass">
        <span v-if="!editing" class="cursor-text" :class="{ 'opacity-60': !text }" @click="startEdit" v-html="formattedText || '提示内容'" />
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none"
          @blur="saveEdit"
          @keydown.escape="cancelEdit"
          @keydown="onEditKeydown"
        />
      </div>

      <!-- 表格 -->
      <div v-else-if="block.type === 'table'" class="my-2 overflow-x-auto">
        <table class="w-full border-collapse text-sm" @click="startEdit">
          <thead v-if="tableData.headers.length">
            <tr class="bg-slate-50">
              <th v-for="(h, hi) in tableData.headers" :key="hi" class="border border-slate-200 px-3 py-2 text-left font-semibold text-slate-600">
                <span v-html="renderInlineMarkdown(h)" />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in tableData.rows" :key="ri" class="hover:bg-slate-50/50">
              <td v-for="(cell, ci) in row" :key="ci" class="border border-slate-200 px-3 py-2 text-slate-700" v-html="renderInlineMarkdown(cell)" />
            </tr>
          </tbody>
        </table>
        <div v-if="!tableData.headers.length" class="px-4 py-3 bg-slate-50 rounded-xl text-sm text-slate-400 text-center cursor-pointer" @click="startEdit">
          📊 点击编辑表格（格式：| 列1 | 列2 |）
        </div>
      </div>

      <!-- 默认/未知 -->
      <div v-else class="text-sm text-slate-400 py-1">[{{ block.type }}]</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
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
const editLanguage = ref('')
const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

// 新创建的空 block 自动进入编辑模式
onMounted(() => {
  const contentText = String(props.block.content.text || props.block.content.code || props.block.content.url || '')
  const hasTableHeaders = Array.isArray(props.block.content.headers) && (props.block.content.headers as unknown[]).length > 0
  if (!contentText && !hasTableHeaders && ['paragraph', 'heading', 'quote', 'callout', 'list', 'code', 'image', 'table'].includes(props.block.type)) {
    startEdit()
  }
})

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
const imageUrl = computed(() => String(props.block.content.url || ''))
const imageAlt = computed(() => String(props.block.content.alt || ''))
const isTask = computed(() => Boolean(props.block.content.task))
const listItems = computed(() => {
  const raw = props.block.content.items
  if (Array.isArray(raw)) {
    return raw.map((item: unknown) => {
      if (typeof item === 'object' && item !== null) return item as { text: string; checked?: boolean }
      return { text: String(item), checked: false }
    })
  }
  return []
})
const tableData = computed(() => ({
  headers: (props.block.content.headers as string[]) || [],
  rows: (props.block.content.rows as string[][]) || [],
}))

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
  { type: 'table', label: '表格 ▦', icon: '▦' },
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
  if (['paragraph', 'heading', 'quote', 'callout', 'list', 'code', 'image', 'table'].includes(props.block.type)) {
    editing.value = true
    if (props.block.type === 'code') {
      editText.value = code.value
      editLanguage.value = language.value
    } else if (props.block.type === 'image') {
      editText.value = String(props.block.content.url || '')
    } else if (props.block.type === 'table') {
      const hdrs = tableData.value.headers.join(' | ')
      editText.value = hdrs ? `| ${hdrs} |` : ''
    } else {
      editText.value = text.value
    }
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

  if (props.block.type === 'image') {
    if (newText !== String(props.block.content.url || '')) {
      emit('save', { ...props.block.content, url: newText, alt: '' })
    }
    return
  }

  if (props.block.type === 'table') {
    const tableMatch = newText.match(/^\|(.+)\|$/)
    if (tableMatch) {
      const headers = tableMatch[1].split('|').map(h => h.trim()).filter(Boolean)
      if (headers.length >= 2) {
        emit('save', { ...props.block.content, headers })
        return
      }
    }
    cancelEdit()
    return
  }

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

function saveCodeEdit() {
  if (!editing.value) return
  editing.value = false
  const newCode = editText.value
  const newLang = editLanguage.value.trim() || 'text'
  if (newCode !== code.value || newLang !== language.value) {
    emit('save', { ...props.block.content, code: newCode, language: newLang })
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

// ===== 行内 Markdown → HTML 渲染 =====
function renderInlineMarkdown(text: string): string {
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // 图片 ![...](...)
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="inline max-w-full rounded" loading="lazy" />')
  // 链接 [...](...)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-brand-600 underline decoration-brand-300 hover:decoration-brand-600" target="_blank" rel="noopener">$1</a>')
  // 粗体 **...** 或 __...__
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold">$1</strong>')
  html = html.replace(/__([^_]+)__/g, '<strong class="font-semibold">$1</strong>')
  // 斜体 *...*
  html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
  // 删除线 ~~...~~
  html = html.replace(/~~([^~]+)~~/g, '<del class="line-through text-slate-400">$1</del>')
  // 高亮 ==...==
  html = html.replace(/==([^=]+)==/g, '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>')
  // 行内代码 `...`
  html = html.replace(/`([^`]+)`/g, '<code class="bg-slate-100 text-pink-600 px-1 py-0.5 rounded text-[0.9em] font-mono">$1</code>')
  // 软换行 \n → <br>
  html = html.replace(/\n/g, '<br />')
  return html
}

const formattedText = computed(() => renderInlineMarkdown(text.value))
const formattedListText = computed(() => renderInlineMarkdown(listText.value))
const placeholderClass = 'text-slate-400 select-none'

// ===== 编辑模式键盘快捷键 =====
function onEditKeydown(e: KeyboardEvent) {
  const ctrl = e.ctrlKey || e.metaKey
  if (ctrl && e.key === 'b') {
    e.preventDefault(); wrapSelection('**')
  } else if (ctrl && e.key === 'i') {
    e.preventDefault(); wrapSelection('*')
  } else if (ctrl && e.key === 'u') {
    e.preventDefault(); wrapSelection('<u>', '</u>')
  } else if (ctrl && e.key === 'k') {
    e.preventDefault(); insertLink()
  } else if (ctrl && e.shiftKey && e.key === 'K') {
    e.preventDefault(); emit('changeType', 'code')
  } else if (e.key === 'Enter' && e.shiftKey) {
    e.preventDefault(); insertAtCursor('\n')
  } else if (ctrl && e.key >= '1' && e.key <= '6') {
    e.preventDefault()
    const lv = parseInt(e.key)
    if (props.block.type !== 'heading' || level.value !== lv) {
      emit('save', { ...props.block.content, text: editText.value, level: lv })
      emit('changeType', 'heading')
    }
  }
}

function wrapSelection(wrapper: string, endWrapper?: string) {
  const el = inputRef.value
  if (!el) return
  const start = el.selectionStart ?? 0
  const end = el.selectionEnd ?? 0
  const before = editText.value.slice(0, start)
  const selected = editText.value.slice(start, end)
  const after = editText.value.slice(end)
  editText.value = before + wrapper + selected + (endWrapper || wrapper) + after
  nextTick(() => {
    el.focus()
    el.setSelectionRange(start + wrapper.length, start + wrapper.length + selected.length)
  })
}

function insertLink() {
  const el = inputRef.value
  if (!el) return
  const start = el.selectionStart ?? 0
  const end = el.selectionEnd ?? 0
  const selected = editText.value.slice(start, end) || '链接文字'
  const url = prompt('输入链接URL:', 'https://')
  if (url) {
    const before = editText.value.slice(0, start)
    const after = editText.value.slice(end)
    editText.value = before + `[${selected}](${url})` + after
    nextTick(() => el.focus())
  }
}

function insertAtCursor(text: string) {
  const el = inputRef.value
  if (!el) return
  const start = el.selectionStart ?? 0
  const before = editText.value.slice(0, start)
  const after = editText.value.slice(start)
  editText.value = before + text + after
  nextTick(() => {
    el.focus()
    const pos = start + text.length
    el.setSelectionRange(pos, pos)
  })
}

function checkMarkdownShortcut(input: string): { type?: string; content: Record<string, unknown> } | null {
  // # 标题
  const hMatch = input.match(/^(#{1,6})\s+(.+)/)
  if (hMatch) {
    return { type: 'heading', content: { level: hMatch[1].length, text: hMatch[2] } }
  }
  // --- / *** / ___ 分割线
  if (/^[-*_]{3,}$/.test(input)) {
    return { type: 'divider', content: {} }
  }
  // - [ ] / - [x] 任务列表
  const taskMatch = input.match(/^[-*+]\s+\[([ xX])\]\s+(.+)/)
  if (taskMatch) {
    return { type: 'list', content: { ordered: false, task: true, items: [{ text: taskMatch[2], checked: taskMatch[1].toLowerCase() === 'x' }] } }
  }
  // - 无序列表
  if (/^[-*+]\s/.test(input)) {
    return { type: 'list', content: { ordered: false, items: [{ text: input.replace(/^[-*+]\s/, '') }] } }
  }
  // 1. 有序列表
  if (/^\d+\.\s/.test(input)) {
    return { type: 'list', content: { ordered: true, items: [{ text: input.replace(/^\d+\.\s/, '') }] } }
  }
  // > 引用
  if (input.startsWith('> ')) {
    return { type: 'quote', content: { text: input.slice(2) } }
  }
  // ``` 代码
  if (input.startsWith('```')) {
    return { type: 'code', content: { language: input.slice(3).trim() || 'text', code: '' } }
  }
  // $$ 数学公式块
  if (input.startsWith('$$')) {
    return { type: 'code', content: { language: 'math', code: '' } }
  }
  // | ... | ... | 表格
  const tableMatch = input.match(/^\|(.+)\|$/)
  if (tableMatch) {
    const headers = tableMatch[1].split('|').map(h => h.trim()).filter(Boolean)
    if (headers.length >= 2) {
      return { type: 'table', content: { headers, rows: [] } }
    }
  }
  return null
}

function navigateToPage() {
  if (pageId.value) emit('navigate', pageId.value)
}

async function copyCode() {
  await navigator.clipboard.writeText(code.value)
}

async function toggleTaskItem(index: number) {
  const items = [...listItems.value]
  if (items[index]) {
    items[index] = { ...items[index], checked: !items[index].checked }
    emit('save', { ...props.block.content, items })
  }
}
</script>

<style scoped>
.block-menu-item {
  @apply w-full flex items-center gap-2 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors text-left;
}
</style>
