<template>
  <div>
    <div
      class="flex items-center gap-1.5 px-2 py-1.5 rounded-lg cursor-pointer text-sm transition-all group"
      :class="[isActive ? 'bg-brand-50 text-brand-700 font-semibold border-l-[3px] border-brand-500 -ml-[3px]' : 'hover:bg-slate-100 text-slate-700 border-l-[3px] border-transparent -ml-[3px]', dragOverClass]"
      :style="{ paddingLeft: `${depth * 12 + 8}px` }"
      draggable="true"
      @click="handleClick"
      @dragstart="onDragStart"
      @dragend="onDragEnd"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
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

      <!-- 重命名模式 -->
      <input
        v-if="isRenaming"
        ref="renameInput"
        v-model="renameTitle"
        class="flex-1 px-1 py-0.5 text-sm bg-white border border-brand-400 rounded outline-none focus:ring-1 focus:ring-brand-400"
        @keyup.enter="confirmRename"
        @keyup.escape="cancelRename"
        @blur="confirmRename"
        @click.stop
      />
      <span v-else class="truncate flex-1">{{ node.title }}</span>

      <span v-if="isLinked" class="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100">🔗</span>

      <!-- "..." 上下文菜单按钮 -->
      <div class="relative shrink-0">
        <button
          class="w-5 h-5 flex items-center justify-center rounded text-slate-400 hover:text-slate-600 hover:bg-slate-200 opacity-0 group-hover:opacity-100 transition-all"
          :class="{ 'opacity-100 bg-slate-200': menuOpen }"
          @click.stop="toggleMenu"
        >
          <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
            <path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zM12 10a2 2 0 11-4 0 2 2 0 014 0zM16 12a2 2 0 100-4 2 2 0 000 4z" />
          </svg>
        </button>

        <!-- 下拉菜单 -->
        <Teleport to="body">
          <div
            v-if="menuOpen"
            class="fixed inset-0 z-40"
            @click="closeMenu"
          />
          <div
            v-if="menuOpen"
            ref="menuRef"
            class="fixed z-50 w-56 bg-white rounded-xl shadow-lg border border-slate-200 py-1 overflow-hidden"
            :style="menuStyle"
            @click.stop
          >
            <!-- 在右侧打开 -->
            <button class="menu-item" @click="action('open')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" /></svg>
              <span>在右侧打开</span>
            </button>

            <div class="my-1 border-t border-slate-100" />

            <!-- 移动到 -->
            <div class="relative" @mouseenter="showMoveTo = true" @mouseleave="showMoveTo = false">
              <button class="menu-item w-full justify-between">
                <span class="flex items-center gap-2.5">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7.5L7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5" /></svg>
                  <span>移动到</span>
                </span>
                <svg class="w-3 h-3 text-slate-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
              </button>
              <!-- 子菜单：选择目标父页面 -->
              <div v-if="showMoveTo" class="sub-menu">
                <button class="menu-item text-xs" @click="action('move', null)">
                  <span>📂 根目录（无父级）</span>
                </button>
                <div class="my-0.5 border-t border-slate-50" />
                <button
                  v-for="p in siblingPages"
                  :key="'move-' + p.id"
                  class="menu-item text-xs"
                  @click="action('move', p.id)"
                >
                  <span>{{ p.icon || '📄' }} {{ p.title }}</span>
                </button>
                <div v-if="siblingPages.length === 0" class="px-3 py-2 text-xs text-slate-400">
                  没有其他页面
                </div>
              </div>
            </div>

            <!-- 嵌入到 -->
            <div class="relative" @mouseenter="showEmbedTo = true" @mouseleave="showEmbedTo = false">
              <button class="menu-item w-full justify-between">
                <span class="flex items-center gap-2.5">
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15a2.25 2.25 0 012.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" /></svg>
                  <span>嵌入到</span>
                </span>
                <svg class="w-3 h-3 text-slate-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
              </button>
              <!-- 子菜单：选择嵌入目标页面 -->
              <div v-if="showEmbedTo" class="sub-menu">
                <button
                  v-for="p in siblingPages"
                  :key="'embed-' + p.id"
                  class="menu-item text-xs"
                  @click="action('embed', p.id)"
                >
                  <span>{{ p.icon || '📄' }} {{ p.title }}</span>
                </button>
                <div v-if="siblingPages.length === 0" class="px-3 py-2 text-xs text-slate-400">
                  没有其他页面
                </div>
              </div>
            </div>

            <div class="my-1 border-t border-slate-100" />

            <!-- 复制访问页面引用链接 -->
            <button class="menu-item" @click="action('copyLink')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" /></svg>
              <span>复制页面引用链接</span>
            </button>

            <!-- 复制页面ID -->
            <button class="menu-item" @click="action('copyId')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M5.25 8.25h15m-16.5 7.5h15m-1.8-13.5l-3.9 19.5m-2.1-19.5l-3.9 19.5" /></svg>
              <span>复制页面ID</span>
            </button>

            <div class="my-1 border-t border-slate-100" />

            <!-- 导入目录/文件 -->
            <button class="menu-item" @click="action('import')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>
              <span>导入目录/文件</span>
            </button>

            <!-- 新增子页面 -->
            <button class="menu-item" @click="action('addSubPage')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <span>新增子页面</span>
            </button>

            <!-- 拷贝副本 -->
            <button class="menu-item" @click="action('duplicate')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15.75 17.25v3.375c0 .621-.504 1.125-1.125 1.125h-9.75a1.125 1.125 0 01-1.125-1.125V7.875c0-.621.504-1.125 1.125-1.125H6.75a9.06 9.06 0 011.5.124m7.5 10.376h3.375c.621 0 1.125-.504 1.125-1.125V11.25c0-4.46-3.243-8.161-7.5-8.876a9.06 9.06 0 00-1.5-.124H9.375c-.621 0-1.125.504-1.125 1.125v3.5m7.5 10.375H9.375a1.125 1.125 0 01-1.125-1.125v-9.25m12 6.625v-1.875a3.375 3.375 0 00-3.375-3.375h-1.5a1.125 1.125 0 01-1.125-1.125v-1.5a3.375 3.375 0 00-3.375-3.375H9.75" /></svg>
              <span>拷贝副本</span>
            </button>

            <!-- 重命名 -->
            <button class="menu-item" @click="action('rename')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" /></svg>
              <span>重命名</span>
            </button>

            <!-- 删除 -->
            <button class="menu-item text-red-600 hover:bg-red-50" @click="action('delete')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" /></svg>
              <span>删除</span>
            </button>
          </div>
        </Teleport>
      </div>
    </div>

    <template v-if="expanded && hasChildren">
      <PageTreeNode
        v-for="child in node.children"
        :key="'c-' + child.id"
        :node="child"
        :active-id="activeId"
        :all-pages="allPages"
        :depth="depth + 1"
        @select="$emit('select', $event)"
        @action="(type, payload) => $emit('action', type, payload)"
      />
      <PageTreeNode
        v-for="linked in node.linked_children"
        :key="'l-' + linked.id"
        :node="linked"
        :active-id="activeId"
        :all-pages="allPages"
        :depth="depth + 1"
        :is-linked="true"
        @select="$emit('select', $event)"
        @action="(type, payload) => $emit('action', type, payload)"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import type { PageTreeNode as TreeNode } from '@/types'

const props = defineProps<{
  node: TreeNode
  activeId?: number | null
  depth?: number
  isLinked?: boolean
  allPages?: TreeNode[]
}>()

const emit = defineEmits<{
  select: [id: number]
  action: [type: string, payload?: Record<string, unknown>]
}>()

// 当 activeId 变化或初始化时，自动展开包含 active 页面的路径
const expanded = ref(true)

// 检查当前节点的后代中是否包含 active 页面
function hasActiveInDescendants(): boolean {
  if (!props.activeId) return false
  function check(nodes: TreeNode[] | undefined): boolean {
    if (!nodes) return false
    for (const n of nodes) {
      if (n.id === props.activeId) return true
      if (check(n.children)) return true
      if (check(n.linked_children)) return true
    }
    return false
  }
  return check(props.node.children) || check(props.node.linked_children)
}

// 如果后代中包含 active 页面，保持展开
watch(() => props.activeId, () => {
  if (hasActiveInDescendants() || props.activeId === props.node.id) {
    expanded.value = true
  }
}, { immediate: true })
const depth = computed(() => props.depth ?? 0)
const isActive = computed(() => props.activeId === props.node.id)
const hasChildren = computed(
  () => (props.node.children?.length ?? 0) + (props.node.linked_children?.length ?? 0) > 0,
)

// 上下文菜单位置
const menuOpen = ref(false)
const menuRef = ref<HTMLElement>()
const menuStyle = ref<Record<string, string>>({})
function toggleMenu(e: MouseEvent) {
  if (menuOpen.value) {
    closeMenu()
    return
  }
  const target = e.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  menuStyle.value = {
    top: `${rect.bottom + 4}px`,
    left: `${Math.min(rect.left, window.innerWidth - 240)}px`,
  }
  menuOpen.value = true
  // 等待 Teleport 渲染后微调视口方向
  nextTick(() => {
    if (!menuRef.value) return
    const popupRect = menuRef.value.getBoundingClientRect()
    let newTop: string | undefined
    let newLeft: string | undefined
    if (popupRect.bottom > window.innerHeight - 8) {
      newTop = `${Math.max(4, rect.top - popupRect.height - 4)}px`
    }
    if (popupRect.right > window.innerWidth - 8) {
      newLeft = `${Math.max(4, window.innerWidth - popupRect.width - 8)}px`
    }
    if (newTop || newLeft) {
      menuStyle.value = {
        ...menuStyle.value,
        ...(newTop ? { top: newTop } : {}),
        ...(newLeft ? { left: newLeft } : {}),
      }
    }
  })
}
function closeMenu() {
  menuOpen.value = false
  showMoveTo.value = false
  showEmbedTo.value = false
}

// 子菜单状态
const showMoveTo = ref(false)
const showEmbedTo = ref(false)

// 同级页面（排除自身用于移动/嵌入）
const siblingPages = computed(() => {
  if (!props.allPages) return []
  return props.allPages.filter(p => p.id !== props.node.id)
})

// ===== 拖拽排序与嵌入 =====
const isDragging = ref(false)
const dragOverState = ref<'above' | 'below' | 'inside' | null>(null)

const dragOverClass = computed(() => {
  if (isDragging.value) return 'opacity-30'
  if (dragOverState.value === 'above') return 'border-t-2 border-brand-400'
  if (dragOverState.value === 'below') return 'border-b-2 border-brand-400'
  if (dragOverState.value === 'inside') return 'bg-brand-100 ring-2 ring-brand-300'
  return ''
})

function onDragStart(e: DragEvent) {
  if (!e.dataTransfer) return
  isDragging.value = true
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('application/page-id', String(props.node.id))
}

function onDragEnd() {
  isDragging.value = false
  dragOverState.value = null
}

function onDragOver(e: DragEvent) {
  if (!e.dataTransfer) return
  const myId = String(props.node.id)
  const sourceId = e.dataTransfer.getData('application/page-id')
  if (!sourceId || sourceId === myId) return
  e.dataTransfer.dropEffect = 'move'

  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const y = e.clientY
  const topZone = rect.top + rect.height * 0.25
  const bottomZone = rect.top + rect.height * 0.75

  if (y < topZone) {
    dragOverState.value = 'above'
  } else if (y > bottomZone) {
    dragOverState.value = 'below'
  } else {
    dragOverState.value = 'inside'
  }
}

function onDragLeave() {
  dragOverState.value = null
}

function onDrop(e: DragEvent) {
  const sourceId = e.dataTransfer?.getData('application/page-id')
  const position = dragOverState.value || 'below'
  dragOverState.value = null
  if (!sourceId || sourceId === String(props.node.id)) return

  if (position === 'inside') {
    // 拖入作为子页面：修改 source 的 parent_id 为目标页面 id
    emit('action', 'move', { pageId: Number(sourceId), parentId: props.node.id })
  } else {
    // 同级排序：通过 sort_order 调整
    emit('action', 'reorder', { pageId: Number(sourceId), targetId: props.node.id, position })
  }
}

// 重命名状态
const isRenaming = ref(false)
const renameTitle = ref('')
const renameInput = ref<HTMLInputElement>()

function handleClick() {
  if (!isRenaming.value) {
    emit('select', props.node.id)
  }
}

async function action(type: string, targetId?: number | null) {
  closeMenu()
  switch (type) {
    case 'open':
      emit('select', props.node.id)
      break
    case 'move':
      emit('action', 'move', { pageId: props.node.id, parentId: targetId ?? null })
      break
    case 'embed':
      emit('action', 'embed', { pageId: props.node.id, targetId })
      break
    case 'copyLink': {
      const url = `${window.location.origin}/notes/${props.node.slug}`
      await navigator.clipboard.writeText(url)
      break
    }
    case 'copyId':
      await navigator.clipboard.writeText(String(props.node.id))
      break
    case 'import':
      emit('action', 'import', { pageId: props.node.id })
      break
    case 'addSubPage':
      emit('action', 'addSubPage', { pageId: props.node.id })
      break
    case 'duplicate':
      emit('action', 'duplicate', { pageId: props.node.id })
      break
    case 'rename':
      isRenaming.value = true
      renameTitle.value = props.node.title
      await nextTick()
      renameInput.value?.focus()
      renameInput.value?.select()
      break
    case 'delete':
      emit('action', 'delete', { pageId: props.node.id, title: props.node.title })
      break
  }
}

async function confirmRename() {
  if (!isRenaming.value) return
  const title = renameTitle.value.trim()
  isRenaming.value = false
  if (title && title !== props.node.title) {
    emit('action', 'rename', { pageId: props.node.id, title })
  }
}

function cancelRename() {
  isRenaming.value = false
}
</script>

<style scoped>
.menu-item {
  @apply w-full flex items-center gap-2.5 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors text-left;
}

.sub-menu {
  @apply absolute left-full top-0 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1 ml-1 max-h-48 overflow-y-auto;
}
</style>
