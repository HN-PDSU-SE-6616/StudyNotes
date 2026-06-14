<template>
  <aside class="w-64 bg-white border-r border-slate-200 flex flex-col h-full shrink-0">
    <!-- Logo -->
    <div class="p-5 border-b border-slate-100">
      <div class="flex items-center gap-2.5">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center">
          <span class="text-white text-lg font-bold">T</span>
        </div>
        <div>
          <h1 class="font-bold text-slate-800">Taot 知识库</h1>
          <p class="text-[11px] text-slate-400">Personal Knowledge Base</p>
        </div>
      </div>
    </div>

    <!-- 导航 -->
    <nav class="flex-1 p-3 space-y-1">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ 'nav-item-active': isActive(item.path) }"
      >
        <component :is="item.icon" class="w-5 h-5 shrink-0" />
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- 用户 -->
    <div class="p-4 border-t border-slate-100">
      <div class="flex items-center gap-3 p-2 rounded-xl hover:bg-slate-50 transition-colors">
        <UserAvatar :name="auth.displayName" :url="auth.avatarUrl" size="sm" :show-info="true" subtitle="在线" />
      </div>
      <button
        @click="handleLogout"
        class="mt-2 w-full text-left px-3 py-2 text-sm text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-xl transition-all"
      >
        退出登录
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import UserAvatar from '@/components/common/UserAvatar.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const HomeIcon = () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25' }),
])

const NotesIcon = () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z' }),
])

const GraphIcon = () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor', 'stroke-width': '1.5' }, [
  h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', d: 'M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5' }),
])

const navItems = [
  { path: '/', label: '首页热点', icon: HomeIcon },
  { path: '/notes', label: '我的笔记', icon: NotesIcon },
  { path: '/graph', label: '关系图谱', icon: GraphIcon },
]

function isActive(path: string) {
  if (path === '/') return route.path === '/'
  return route.path.startsWith(path)
}

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>
