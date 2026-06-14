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
        @select="$emit('select', $event)"
      />
    </div>

    <!-- 底部返回首页 -->
    <div class="p-3 border-t border-slate-100">
      <router-link to="/" class="nav-item w-full">
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75" /></svg>
        返回首页
      </router-link>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { usePageStore } from '@/stores/page'
import UserAvatar from '@/components/common/UserAvatar.vue'
import PageTreeNode from './PageTreeNode.vue'

defineProps<{ activeId?: number | null }>()
defineEmits<{ select: [id: number]; create: [] }>()

const auth = useAuthStore()
const pageStore = usePageStore()
const searchInput = ref('')

let searchTimer: ReturnType<typeof setTimeout>
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => pageStore.searchPages(searchInput.value), 300)
}
</script>
