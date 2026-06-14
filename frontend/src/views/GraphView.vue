<template>
  <div class="h-screen flex overflow-hidden">
    <AppSidebar />
    <main class="flex-1 flex items-center justify-center bg-slate-50">
      <div class="text-center max-w-md">
        <div class="w-20 h-20 rounded-2xl bg-brand-50 flex items-center justify-center mx-auto mb-6">
          <svg class="w-10 h-10 text-brand-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
          </svg>
        </div>
        <h2 class="text-xl font-bold text-slate-800 mb-2">页面关系图</h2>
        <p class="text-sm text-slate-500 mb-6">可视化展示页面之间的链接关系，即将上线</p>
        <router-link to="/notes" class="btn-primary inline-block w-auto px-8">
          返回我的笔记
        </router-link>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import AppSidebar from '@/components/layout/AppSidebar.vue'
</script>
