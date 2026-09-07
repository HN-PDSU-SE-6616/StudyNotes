<script setup lang="ts">
import { ref } from 'vue'
import { ragApi } from '@/api/files'
import { useOrgStore } from '@/stores/org'
import type { RagResult, RagSource } from '@/types'

const emit = defineEmits<{ close: []; openSource: [src: RagSource] }>()

const orgStore = useOrgStore()
const question = ref('')
const loading = ref(false)
const error = ref('')
const result = ref<RagResult | null>(null)

async function ask() {
  if (!question.value.trim() || loading.value) return
  loading.value = true
  error.value = ''
  try {
    const { data } = await ragApi.ask(question.value, orgStore.activeProject?.id, 8)
    result.value = data
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail || '问答失败，请确认已配置 Embedding 模型与 LLM Key'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex flex-col h-full bg-white">
    <header class="px-4 py-3 border-b border-slate-100 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-2">
        <span class="w-7 h-7 rounded-lg bg-brand-50 flex items-center justify-center">
          <svg class="w-4 h-4 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h8M8 14h4M9 17H7a2 2 0 01-2-2V5a2 2 0 012-2h10a2 2 0 012 2v10a2 2 0 01-2 2h-2l-4 4v-4" />
          </svg>
        </span>
        <h3 class="text-sm font-semibold text-slate-800">AI 知识问答</h3>
      </div>
      <button class="w-7 h-7 flex items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100"
        title="关闭" @click="$emit('close')">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </header>

    <div class="flex-1 overflow-y-auto p-4 space-y-3 text-sm">
      <p v-if="!result" class="text-slate-400 leading-6">
        基于当前项目（{{ orgStore.activeProject?.name || '未选择' }}）内容问答，支持跳转到笔记原文。
      </p>

      <div v-if="error" class="text-amber-700 bg-amber-50 rounded-xl px-4 py-3">{{ error }}</div>

      <template v-if="result">
        <div class="prose-sm text-slate-700 whitespace-pre-wrap leading-7 border border-slate-100 rounded-xl p-4 bg-slate-50/60">
          {{ result.answer }}
        </div>

        <div v-if="result.sources.length" class="pt-2">
          <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">引用来源（{{ result.sources.length }}）</div>
          <div class="space-y-2">
            <button
              v-for="(s, i) in result.sources"
              :key="s.note_id + '-' + i"
              class="w-full text-left rounded-xl border border-slate-200 hover:border-brand-300 hover:bg-brand-50/40 transition-colors px-3 py-2.5"
              @click="$emit('openSource', s)"
            >
              <div class="flex items-center gap-2">
                <span class="text-[10px] font-bold text-brand-600 bg-brand-50 rounded px-1.5 py-0.5">{{ i + 1 }}</span>
                <span class="text-sm font-medium text-slate-700 truncate">{{ s.title }}</span>
                <span class="ml-auto text-[10px] text-slate-400 shrink-0">{{ (s.score * 100).toFixed(1) }}%</span>
              </div>
              <div v-if="s.heading_path" class="text-xs text-brand-600 mt-1">{{ s.heading_path }}</div>
              <div class="text-xs text-slate-400 line-clamp-2 mt-1">{{ s.excerpt }}</div>
            </button>
          </div>
        </div>
      </template>
    </div>

    <footer class="border-t border-slate-100 p-3 shrink-0">
      <div class="flex gap-2">
        <input
          v-model="question"
          type="text"
          class="flex-1 min-w-0 px-3 py-2 rounded-xl bg-slate-50 border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          placeholder="向知识库提问…"
          @keydown.enter="ask"
        />
        <button
          class="px-4 py-2 rounded-xl bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 disabled:opacity-50 transition-colors shrink-0"
          :disabled="loading || !question.trim()"
          @click="ask"
        >
          {{ loading ? '…' : '提问' }}
        </button>
      </div>
    </footer>
  </div>
</template>
