<template>
  <a
    :href="item.url"
    target="_blank"
    rel="noopener noreferrer"
    class="hotspot-card block animate-slide-up"
    :style="{ animationDelay: `${delay}ms` }"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="flex-1 min-w-0">
        <h3 class="font-semibold text-slate-800 group-hover:text-brand-600 transition-colors line-clamp-2 text-sm leading-snug">
          {{ cleanTitle }}
        </h3>
        <p v-if="item.description" class="mt-1.5 text-xs text-slate-500 line-clamp-2">
          {{ item.description }}
        </p>
      </div>
      <span
        class="shrink-0 px-2 py-0.5 text-[10px] font-medium rounded-full"
        :class="badgeClass"
      >
        {{ sourceLabel }}
      </span>
    </div>
    <div v-if="extraText" class="mt-3 flex items-center gap-3 text-xs text-slate-400">
      <span>{{ extraText }}</span>
    </div>
  </a>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HotItem } from '@/types'

const props = defineProps<{
  item: HotItem
  delay?: number
}>()

const cleanTitle = computed(() =>
  props.item.title.replace(/<[^>]+>/g, ''),
)

const sourceLabel = computed(() => ({
  github: 'GitHub',
  bilibili: 'Bilibili',
  hackernews: 'HN',
  v2ex: 'V2EX',
}[props.item.source] || props.item.source))

const badgeClass = computed(() => ({
  github: 'bg-slate-100 text-slate-600',
  bilibili: 'bg-pink-50 text-pink-600',
  hackernews: 'bg-orange-50 text-orange-600',
  v2ex: 'bg-blue-50 text-blue-600',
}[props.item.source] || 'bg-slate-100 text-slate-600'))

const extraText = computed(() => {
  const e = props.item.extra
  if (props.item.source === 'github' && e.stars) return `⭐ ${formatNum(e.stars as number)} · ${e.language || 'N/A'}`
  if (props.item.source === 'bilibili' && e.play) return `▶ ${formatNum(e.play as number)} · ${e.author || ''}`
  if (props.item.source === 'hackernews' && e.score) return `▲ ${e.score}`
  if (props.item.source === 'v2ex' && e.replies) return `💬 ${e.replies} 回复`
  return ''
})

function formatNum(n: number) {
  if (n >= 10000) return `${(n / 10000).toFixed(1)}万`
  return String(n)
}
</script>
