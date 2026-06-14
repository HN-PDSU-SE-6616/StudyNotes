<template>
  <div class="h-screen flex overflow-hidden">
    <AppSidebar />

    <main class="flex-1 overflow-y-auto">
      <!-- 顶部欢迎 -->
      <header class="bg-gradient-to-r from-brand-600 to-purple-600 text-white px-8 py-10">
        <div class="max-w-5xl">
          <p class="text-sm text-white/70 mb-1">{{ greeting }}</p>
          <h1 class="text-3xl font-bold">{{ auth.displayName }}，欢迎回来 👋</h1>
          <p class="mt-2 text-white/80 text-sm">今日热点已为你准备好，探索编程世界的最新动态</p>
        </div>
      </header>

      <div class="max-w-5xl mx-auto px-8 py-8">
        <p v-if="hotspot.error" class="mb-6 text-sm text-amber-700 bg-amber-50 px-4 py-3 rounded-xl">
          {{ hotspot.error }}
        </p>

        <HotspotSection
          title="GitHub 热门项目"
          subtitle="开源社区最受关注的项目"
          icon="⭐"
          icon-bg="bg-slate-100"
          :items="hotspot.data?.github ?? []"
          :loading="hotspot.loading"
        />

        <HotspotSection
          title="B站编程教程"
          subtitle="热门编程学习视频"
          icon="📺"
          icon-bg="bg-pink-50"
          :items="hotspot.data?.bilibili ?? []"
          :loading="hotspot.loading"
        />

        <HotspotSection
          title="编程社区"
          subtitle="Hacker News & V2EX 最新讨论"
          icon="💬"
          icon-bg="bg-blue-50"
          :items="hotspot.data?.community ?? []"
          :loading="hotspot.loading"
        />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useHotspotStore } from '@/stores/hotspot'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import HotspotSection from '@/components/hotspot/HotspotSection.vue'

const auth = useAuthStore()
const hotspot = useHotspotStore()

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
})

onMounted(() => hotspot.fetchHotspots())
</script>
