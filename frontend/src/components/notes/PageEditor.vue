<template>
  <div class="flex-1 flex flex-col h-full bg-white">
    <!-- 顶栏 -->
    <header class="h-14 border-b border-slate-100 flex items-center justify-between px-6 shrink-0">
      <div class="flex items-center gap-3 min-w-0">
        <span class="text-xl">{{ page?.icon || '📄' }}</span>
        <input
          v-if="page"
          :value="page.title"
          class="text-lg font-semibold text-slate-800 bg-transparent border-none outline-none min-w-0"
          @change="onTitleChange"
        />
      </div>
      <div class="flex items-center gap-2">
        <div class="relative" ref="menuRef">
          <button
            class="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-slate-50 hover:bg-slate-100 rounded-xl transition-colors text-slate-600"
            @click="showMenu = !showMenu"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
            添加 Block
          </button>
          <div
            v-if="showMenu"
            class="absolute right-0 top-full mt-1 w-48 bg-white rounded-xl shadow-xl border border-slate-100 py-1 z-10"
          >
            <button
              v-for="bt in blockTypes"
              :key="bt.type"
              class="w-full text-left px-4 py-2 text-sm hover:bg-slate-50 flex items-center gap-2"
              @click="addBlock(bt.type, bt.default)"
            >
              <span>{{ bt.icon }}</span>
              {{ bt.label }}
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- 内容区 -->
    <div class="flex-1 overflow-y-auto">
      <div v-if="!page" class="flex items-center justify-center h-full text-slate-400">
        <div class="text-center">
          <div class="text-5xl mb-4">📝</div>
          <p class="text-lg font-medium text-slate-500">选择或创建一个页面</p>
          <p class="text-sm mt-1">从左侧侧边栏开始你的知识之旅</p>
        </div>
      </div>

      <div v-else-if="pageStore.loading" class="flex items-center justify-center h-full">
        <div class="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>

      <div v-else class="max-w-3xl mx-auto px-8 py-8">
        <BlockRenderer
          v-for="block in page.blocks"
          :key="block.id"
          :block="block"
          @save="(c) => onBlockSave(block.id, c)"
          @navigate="(id) => $emit('navigate', id)"
        />

        <button
          v-if="page"
          class="mt-4 w-full py-3 text-sm text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-xl transition-all border border-dashed border-slate-200"
          @click="addBlock('paragraph', { text: '' })"
        >
          + 点击添加内容
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePageStore } from '@/stores/page'
import { pagesApi } from '@/api/pages'
import BlockRenderer from './BlockRenderer.vue'

const emit = defineEmits<{ navigate: [id: number] }>()

const pageStore = usePageStore()
const showMenu = ref(false)
const menuRef = ref<HTMLElement | null>(null)

const page = computed(() => pageStore.currentPage)

const blockTypes = [
  { type: 'paragraph', label: '段落', icon: '¶', default: { text: '' } },
  { type: 'heading', label: '标题', icon: 'H', default: { level: 2, text: '' } },
  { type: 'code', label: '代码', icon: '</>', default: { language: 'python', code: '' } },
  { type: 'quote', label: '引用', icon: '❝', default: { text: '' } },
  { type: 'divider', label: '分割线', icon: '—', default: {} },
  { type: 'callout', label: '提示框', icon: '💡', default: { type: 'info', text: '提示内容' } },
  { type: 'page_link', label: '页面链接', icon: '🔗', default: { page_id: 0, title: '链接页面' } },
]

function onClickOutside(e: MouseEvent) {
  if (menuRef.value && !menuRef.value.contains(e.target as Node)) {
    showMenu.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside))
onUnmounted(() => document.removeEventListener('click', onClickOutside))

async function addBlock(type: string, content: Record<string, unknown>) {
  if (!page.value) return
  showMenu.value = false
  await pageStore.addBlock(page.value.id, type, content)
}

async function onBlockSave(blockId: number, content: Record<string, unknown>) {
  await pageStore.updateBlock(blockId, { content })
}

async function onTitleChange(e: Event) {
  if (!page.value) return
  const title = (e.target as HTMLInputElement).value
  await pagesApi.update(page.value.id, { title })
  page.value.title = title
  await pageStore.fetchTree()
}
</script>
