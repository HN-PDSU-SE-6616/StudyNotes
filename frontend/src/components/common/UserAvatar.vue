<template>
  <div class="flex items-center gap-3" :class="sizeClass">
    <div
      class="rounded-full bg-gradient-to-br from-brand-500 to-purple-600 flex items-center justify-center text-white font-semibold shrink-0 overflow-hidden"
      :class="avatarSize"
    >
      <img v-if="url" :src="url" :alt="name" class="w-full h-full object-cover" />
      <span v-else>{{ initial }}</span>
    </div>
    <div v-if="showInfo" class="min-w-0">
      <p class="font-medium text-slate-800 truncate" :class="nameSize">{{ name }}</p>
      <p v-if="subtitle" class="text-xs text-slate-500 truncate">{{ subtitle }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  name: string
  url?: string | null
  subtitle?: string
  size?: 'sm' | 'md' | 'lg'
  showInfo?: boolean
}>(), {
  size: 'md',
  showInfo: true,
})

const initial = computed(() => props.name.charAt(0).toUpperCase())

const avatarSize = computed(() => ({
  sm: 'w-8 h-8 text-sm',
  md: 'w-10 h-10 text-base',
  lg: 'w-12 h-12 text-lg',
}[props.size]))

const nameSize = computed(() => ({
  sm: 'text-sm',
  md: 'text-sm',
  lg: 'text-base',
}[props.size]))

const sizeClass = computed(() => props.showInfo ? '' : '')
</script>
