<template>
  <Teleport to="body">
    <!-- 遮罩层 -->
    <div v-if="visible" class="fixed inset-0 z-40 bg-black/10" @click="$emit('close')" />
    <!-- 右侧面板 -->
    <div
      v-if="visible"
      class="fixed right-0 top-0 bottom-0 z-50 w-80 bg-white shadow-2xl border-l border-slate-200 flex flex-col transition-transform duration-300"
      :class="visible ? 'translate-x-0' : 'translate-x-full'"
    >
      <!-- 标题栏 -->
      <div class="h-14 border-b border-slate-100 flex items-center justify-between px-4 shrink-0">
        <h3 class="text-sm font-semibold text-slate-700">页面设置</h3>
        <button
          class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors"
          @click="$emit('close')"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
        </button>
      </div>

      <!-- 内容区 -->
      <div class="flex-1 overflow-y-auto px-4 py-4 space-y-6">
        <!-- ===== 显示设置 ===== -->
        <section>
          <h4 class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-3">显示</h4>
          <div class="space-y-3">
            <!-- 自适应宽度 -->
            <label class="flex items-center justify-between cursor-pointer">
              <span class="text-sm text-slate-700">自适应宽度</span>
              <button
                class="relative w-9 h-5 rounded-full transition-colors"
                :class="settings.adaptiveWidth ? 'bg-brand-500' : 'bg-slate-300'"
                @click="toggle('adaptiveWidth')"
              >
                <span class="absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform" :class="settings.adaptiveWidth ? 'left-4 translate-x-0.5' : 'left-0.5'" />
              </button>
            </label>
            <!-- 小字体 -->
            <label class="flex items-center justify-between cursor-pointer">
              <span class="text-sm text-slate-700">小字体</span>
              <button
                class="relative w-9 h-5 rounded-full transition-colors"
                :class="settings.smallFont ? 'bg-brand-500' : 'bg-slate-300'"
                @click="toggle('smallFont')"
              >
                <span class="absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform" :class="settings.smallFont ? 'left-4 translate-x-0.5' : 'left-0.5'" />
              </button>
            </label>
            <!-- 标题目录 -->
            <label class="flex items-center justify-between cursor-pointer">
              <span class="text-sm text-slate-700">标题目录</span>
              <button
                class="relative w-9 h-5 rounded-full transition-colors"
                :class="settings.showToc ? 'bg-brand-500' : 'bg-slate-300'"
                @click="toggle('showToc')"
              >
                <span class="absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform" :class="settings.showToc ? 'left-4 translate-x-0.5' : 'left-0.5'" />
              </button>
            </label>
            <!-- 标题自动编号 -->
            <label class="flex items-center justify-between cursor-pointer">
              <span class="text-sm text-slate-700">标题自动编号</span>
              <button
                class="relative w-9 h-5 rounded-full transition-colors"
                :class="settings.autoNumbering ? 'bg-brand-500' : 'bg-slate-300'"
                @click="toggle('autoNumbering')"
              >
                <span class="absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform" :class="settings.autoNumbering ? 'left-4 translate-x-0.5' : 'left-0.5'" />
              </button>
            </label>
          </div>
        </section>

        <!-- ===== 页面统计 ===== -->
        <section>
          <h4 class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-3">页面统计</h4>
          <div v-if="statsLoading" class="text-sm text-slate-400 py-2">加载中...</div>
          <div v-else-if="stats" class="space-y-2 text-sm">
            <div class="flex justify-between py-1 border-b border-slate-50">
              <span class="text-slate-500">总字数</span>
              <span class="text-slate-700 font-mono">{{ stats.total_words.toLocaleString() }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-50">
              <span class="text-slate-500">块个数</span>
              <span class="text-slate-700 font-mono">{{ stats.block_count }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-50">
              <span class="text-slate-500">浏览量</span>
              <span class="text-slate-700 font-mono">{{ stats.view_count }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-50">
              <span class="text-slate-500">创建时间</span>
              <span class="text-slate-700 text-xs">{{ formatDate(stats.created_at) }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-50">
              <span class="text-slate-500">创建者</span>
              <span class="text-slate-700">{{ stats.creator_name || '-' }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-50">
              <span class="text-slate-500">最后编辑</span>
              <span class="text-slate-700 text-xs">{{ formatDate(stats.updated_at) }}</span>
            </div>
            <div class="flex justify-between py-1 border-b border-slate-50">
              <span class="text-slate-500">编辑者</span>
              <span class="text-slate-700">{{ stats.last_editor_name || '-' }}</span>
            </div>
          </div>
        </section>

        <!-- ===== 占位：未来功能 ===== -->
        <section>
          <h4 class="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-3">更多操作</h4>
          <div class="space-y-1">
            <button v-for="item in futureActions" :key="item.label"
              class="w-full flex items-center gap-2 px-2 py-1.5 text-sm text-slate-400 rounded hover:bg-slate-50 transition-colors text-left cursor-not-allowed"
              :title="item.tip"
            >
              <span class="w-5 text-center text-xs">{{ item.icon }}</span>
              <span>{{ item.label }}</span>
            </button>
          </div>
        </section>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { pagesApi } from '@/api/pages'
import type { PageDetail, PageStats } from '@/types'

// ---- 设置持久化到 localStorage ----
const STORAGE_KEY = 'page-settings'

export interface PageSettings {
  adaptiveWidth: boolean
  smallFont: boolean
  showToc: boolean
  autoNumbering: boolean
}

const defaultSettings: PageSettings = {
  adaptiveWidth: false,
  smallFont: false,
  showToc: false,
  autoNumbering: false,
}

function loadSettings(): PageSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) return { ...defaultSettings, ...JSON.parse(raw) }
  } catch { /* ignore */ }
  return { ...defaultSettings }
}

function saveSettings(s: PageSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s))
}

const props = defineProps<{
  visible: boolean
  page: PageDetail | null
}>()

const emit = defineEmits<{
  close: []
  updateSettings: [settings: PageSettings]
}>()

const settings = ref<PageSettings>(loadSettings())

// 暴露给父组件
defineExpose({ settings })

watch(settings, (s) => {
  saveSettings(s)
  emit('updateSettings', { ...s })
}, { deep: true })

function toggle(key: keyof PageSettings) {
  settings.value[key] = !settings.value[key]
}

// ---- 页面统计 ----
const stats = ref<PageStats | null>(null)
const statsLoading = ref(false)

watch(() => props.page?.id, async (pageId) => {
  if (!pageId || !props.visible) return
  statsLoading.value = true
  try {
    const { data } = await pagesApi.stats(pageId)
    stats.value = data
  } catch {
    stats.value = null
  } finally {
    statsLoading.value = false
  }
}, { immediate: true })

watch(() => props.visible, async (v) => {
  if (v && props.page?.id) {
    statsLoading.value = true
    try {
      const { data } = await pagesApi.stats(props.page.id)
      stats.value = data
    } catch {
      stats.value = null
    } finally {
      statsLoading.value = false
    }
  }
})

// ---- 工具函数 ----
function formatDate(iso: string): string {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

// ---- 占位操作 ----
const futureActions = [
  { icon: '🔒', label: '编辑保护', tip: '即将推出' },
  { icon: '↩️', label: '撤回', tip: '即将推出' },
  { icon: '🗑️', label: '删除页面', tip: '在页面菜单中操作' },
  { icon: '📁', label: '移动到', tip: '即将推出' },
  { icon: '📌', label: '嵌入到', tip: '即将推出' },
  { icon: '🖨️', label: '打印', tip: '即将推出' },
  { icon: '📋', label: '复制链接', tip: '即将推出' },
  { icon: '📤', label: '导出', tip: '即将推出' },
  { icon: '🕒', label: '历史版本', tip: '即将推出' },
  { icon: '🌐', label: '公开设置', tip: '即将推出' },
]
</script>
