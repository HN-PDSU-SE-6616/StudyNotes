<template>
  <section class="mb-10">
    <div class="flex items-center gap-3 mb-5">
      <div
        class="w-10 h-10 rounded-xl flex items-center justify-center text-xl"
        :class="iconBg"
      >
        {{ icon }}
      </div>
      <div>
        <h2 class="text-lg font-bold text-slate-800">{{ title }}</h2>
        <p class="text-xs text-slate-400">{{ subtitle }}</p>
      </div>
    </div>

    <div v-if="loading" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div v-for="i in 4" :key="i" class="h-28 bg-slate-100 rounded-2xl animate-pulse" />
    </div>

    <div v-else-if="items.length" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <HotspotCard
        v-for="(item, idx) in items"
        :key="item.url"
        :item="item"
        :delay="idx * 60"
      />
    </div>

    <div v-else class="text-center py-12 text-slate-400 text-sm bg-slate-50 rounded-2xl">
      暂无数据
    </div>
  </section>
</template>

<script setup lang="ts">
import type { HotItem } from '@/types'
import HotspotCard from './HotspotCard.vue'

defineProps<{
  title: string
  subtitle: string
  icon: string
  iconBg: string
  items: HotItem[]
  loading?: boolean
}>()
</script>
