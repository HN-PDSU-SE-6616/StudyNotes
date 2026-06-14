<template>
  <div class="block-item group relative" @click="$emit('focus')">
    <!-- 段落 -->
    <div v-if="block.type === 'paragraph'" class="py-1">
      <p
        v-if="!editing"
        class="text-slate-700 leading-relaxed whitespace-pre-wrap cursor-text min-h-[1.5em]"
        @click="startEdit"
      >
        {{ text || '点击输入内容...' }}
      </p>
      <textarea
        v-else
        ref="inputRef"
        v-model="editText"
        class="w-full resize-none bg-transparent border-none outline-none text-slate-700 leading-relaxed"
        rows="2"
        @blur="saveEdit"
        @keydown.enter.exact.prevent="saveEdit"
      />
    </div>

    <!-- 标题 -->
    <component
      v-else-if="block.type === 'heading'"
      :is="'h' + (level || 2)"
      class="font-bold text-slate-800 py-1 cursor-text"
      :class="headingClass"
      @click="startEdit"
    >
      <span v-if="!editing">{{ text || '标题' }}</span>
      <input
        v-else
        ref="inputRef"
        v-model="editText"
        class="w-full bg-transparent border-none outline-none font-bold"
        @blur="saveEdit"
        @keydown.enter="saveEdit"
      />
    </component>

    <!-- 代码 -->
    <div v-else-if="block.type === 'code'" class="my-2">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-[10px] font-mono text-slate-400 uppercase">{{ language }}</span>
      </div>
      <pre class="bg-slate-900 text-slate-100 rounded-xl p-4 text-sm overflow-x-auto font-mono"><code>{{ code }}</code></pre>
    </div>

    <!-- 引用 -->
    <blockquote
      v-else-if="block.type === 'quote'"
      class="border-l-4 border-brand-300 pl-4 py-1 text-slate-600 italic cursor-text"
      @click="startEdit"
    >
      {{ text || '引用内容' }}
    </blockquote>

    <!-- 分割线 -->
    <hr v-else-if="block.type === 'divider'" class="my-4 border-slate-200" />

    <!-- 页面链接 -->
    <div
      v-else-if="block.type === 'page_link'"
      class="flex items-center gap-2 px-3 py-2 bg-brand-50 rounded-xl text-brand-700 cursor-pointer hover:bg-brand-100 transition-colors my-1"
      @click="$emit('navigate', Number(block.content.page_id))"
    >
      <span>📎</span>
      <span class="font-medium">{{ block.content.title || '子页面' }}</span>
    </div>

    <!-- 提示框 -->
    <div
      v-else-if="block.type === 'callout'"
      class="px-4 py-3 rounded-xl my-1"
      :class="calloutClass"
    >
      {{ text }}
    </div>

    <!-- 默认 -->
    <div v-else class="text-sm text-slate-400 py-1">
      [{{ block.type }}] {{ JSON.stringify(block.content) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import type { Block } from '@/types'

const props = defineProps<{ block: Block; editing?: boolean }>()
const emit = defineEmits<{ focus: []; save: [content: Record<string, unknown>]; navigate: [pageId: number] }>()

const editing = ref(false)
const editText = ref('')
const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

const text = computed(() => String(props.block.content.text || ''))
const code = computed(() => String(props.block.content.code || ''))
const language = computed(() => String(props.block.content.language || 'text'))
const level = computed(() => Number(props.block.content.level || 2))

const headingClass = computed(() => ({
  1: 'text-3xl',
  2: 'text-2xl',
  3: 'text-xl',
}[level.value] || 'text-2xl'))

const calloutClass = computed(() => ({
  info: 'bg-blue-50 text-blue-800',
  warning: 'bg-amber-50 text-amber-800',
  success: 'bg-green-50 text-green-800',
}[String(props.block.content.type || 'info')] || 'bg-blue-50 text-blue-800'))

async function startEdit() {
  if (['paragraph', 'heading', 'quote'].includes(props.block.type)) {
    editing.value = true
    editText.value = text.value
    await nextTick()
    inputRef.value?.focus()
  }
}

function saveEdit() {
  editing.value = false
  if (editText.value !== text.value) {
    emit('save', { ...props.block.content, text: editText.value })
  }
}
</script>
