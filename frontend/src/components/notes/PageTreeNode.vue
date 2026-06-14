<template>
  <div>
    <div
      class="flex items-center gap-1.5 px-2 py-1.5 rounded-lg cursor-pointer text-sm transition-all group"
      :class="isActive ? 'bg-brand-50 text-brand-700' : 'hover:bg-slate-100 text-slate-700'"
      :style="{ paddingLeft: `${depth * 12 + 8}px` }"
      @click="handleClick"
    >
      <button
        v-if="hasChildren"
        class="w-4 h-4 flex items-center justify-center text-slate-400 hover:text-slate-600 shrink-0"
        @click.stop="expanded = !expanded"
      >
        <svg class="w-3 h-3 transition-transform" :class="{ 'rotate-90': expanded }" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" />
        </svg>
      </button>
      <span v-else class="w-4 shrink-0" />
      <span class="shrink-0">{{ node.icon || '📄' }}</span>
      <span class="truncate flex-1">{{ node.title }}</span>
      <span v-if="isLinked" class="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100">🔗</span>
    </div>

    <template v-if="expanded && hasChildren">
      <PageTreeNode
        v-for="child in node.children"
        :key="'c-' + child.id"
        :node="child"
        :active-id="activeId"
        :depth="depth + 1"
        @select="$emit('select', $event)"
      />
      <PageTreeNode
        v-for="linked in node.linked_children"
        :key="'l-' + linked.id"
        :node="linked"
        :active-id="activeId"
        :depth="depth + 1"
        :is-linked="true"
        @select="$emit('select', $event)"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { PageTreeNode as TreeNode } from '@/types'

const props = defineProps<{
  node: TreeNode
  activeId?: number | null
  depth?: number
  isLinked?: boolean
}>()

const emit = defineEmits<{ select: [id: number] }>()

const expanded = ref(true)
const depth = computed(() => props.depth ?? 0)
const isActive = computed(() => props.activeId === props.node.id)
const hasChildren = computed(
  () => (props.node.children?.length ?? 0) + (props.node.linked_children?.length ?? 0) > 0,
)

function handleClick() {
  emit('select', props.node.id)
}
</script>
