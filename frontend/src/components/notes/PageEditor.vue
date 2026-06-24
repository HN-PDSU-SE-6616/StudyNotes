<template>
  <div class="flex-1 flex flex-col h-full bg-white">
    <!-- ===== Header ===== -->
    <header class="h-14 border-b border-slate-100 flex items-center justify-between px-4 shrink-0 gap-3">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <button
          class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-colors shrink-0"
          title="Collapse sidebar"
          @click="$emit('toggleSidebar')"
        >
          <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" /></svg>
        </button>
        <nav v-if="page" class="flex items-center gap-1 min-w-0 text-sm">
          <template v-for="(crumb, i) in breadcrumbs" :key="crumb.id">
            <span v-if="i > 0" class="text-slate-300 shrink-0">/</span>
            <button
              class="truncate max-w-[160px] hover:text-brand-600 transition-colors shrink-0"
              :class="i === breadcrumbs.length - 1 ? 'font-semibold text-slate-800' : 'text-slate-500'"
              :title="crumb.title"
              @click="onNavigateBreadcrumb(crumb)"
            >
              {{ crumb.title }}
            </button>
          </template>
        </nav>
        <span v-else class="text-lg font-semibold text-slate-400">无标题</span>
      </div>
      <div class="flex items-center gap-1 shrink-0">
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg transition-colors"
          :class="page.is_pinned ? 'text-amber-500 bg-amber-50 hover:bg-amber-100' : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600'"
          title="Pin"
          @click="togglePin"
        >
          <svg class="w-4 h-4" :fill="page.is_pinned ? 'currentColor' : 'none'" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" /></svg>
        </button>
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          title="Graph"
          @click="$router.push('/graph')"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" /></svg>
        </button>
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-300 cursor-not-allowed"
          title="Collaboration (coming soon)"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" /></svg>
        </button>
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-300 cursor-not-allowed"
          title="History (coming soon)"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
        </button>
        <button
          v-if="page"
          class="w-8 h-8 flex items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          :class="{ 'bg-slate-100 text-slate-600': showSettingsPanel }"
          title="Page settings"
          @click="showSettingsPanel = !showSettingsPanel"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20"><path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zM12 10a2 2 0 11-4 0 2 2 0 014 0zM16 12a2 2 0 100-4 2 2 0 000 4z" /></svg>
        </button>
      </div>
    </header>

    <!-- ===== Content Area ===== -->
    <div class="flex-1 flex overflow-hidden transition-all duration-300" :style="contentAreaStyle">
      <div class="flex-1 overflow-y-auto" ref="contentAreaRef">
        <!-- Empty state -->
        <div v-if="!page" class="flex items-center justify-center h-full text-slate-400">
          <div class="text-center">
            <div class="text-5xl mb-4">📝</div>
            <p class="text-lg font-medium text-slate-500">选择或创建一个页面</p>
            <p class="text-sm mt-1">从侧边栏开始你的知识之旅</p>
          </div>
        </div>

        <!-- Loading -->
        <div v-else-if="pageStore.loading" class="flex items-center justify-center h-full">
          <div class="w-8 h-8 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
        </div>

        <!-- Page Content -->
        <div v-else :class="['mx-auto px-8 py-8', pageSettings.adaptiveWidth ? 'max-w-full' : 'max-w-3xl', pageSettings.smallFont ? 'text-sm' : '']">

          <!-- ===== TITLE SECTION ===== -->
          <div class="page-title-section mb-8">
            <div class="flex items-start gap-4">
              <!-- Icon Picker Button -->
              <button
                class="relative shrink-0 mt-1 w-12 h-12 flex items-center justify-center rounded-xl hover:bg-slate-100 transition-colors group/icon text-slate-500"
                title="更换图标"
                @click="openIconPicker"
              >
                <!-- Render SVG icon if found in library, otherwise render as emoji/text -->
                <svg v-if="getPageIconPaths(page.icon)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-9 h-9">
                  <path v-for="(p, pi) in getPageIconPaths(page.icon)!" :key="pi" :d="p.d" />
                </svg>
                <span v-else class="text-3xl leading-none">{{ page.icon || '📄' }}</span>
                <svg class="absolute opacity-0 group-hover/icon:opacity-100 w-3 h-3 text-slate-400 translate-x-4 -translate-y-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
              </button>

              <!-- Title Input -->
              <input
                v-model="pageTitle"
                class="flex-1 bg-transparent border-none outline-none text-4xl font-bold text-slate-800 placeholder-slate-300 leading-tight"
                placeholder="无标题"
                @blur="savePageTitle"
                @keydown.enter.prevent="($event.target as HTMLInputElement).blur()"
              />
            </div>
          </div>

          <!-- ===== CONTENT SECTION ===== -->
          <div class="content-blocks">
            <BlockRenderer
              v-for="(block, idx) in page.blocks"
              :key="block.id"
              :block="block"
              :all-pages="flatPages"
              :settings="pageSettings"
              :heading-number="headingNumbers.get(block.id) || ''"
              :content-placeholder="idx === 0 && allBlocksEmpty ? '请输入内容...' : undefined"
              @save="(c) => onBlockSave(block.id, c)"
              @change-type="(t) => onChangeBlockType(block.id, t)"
              @navigate="(id) => $emit('navigate', id)"
              @delete="onBlockDelete(block.id)"
              @duplicate="onBlockDuplicate(block.id)"
              @move-up="onBlockMove(idx, -1)"
              @move-down="onBlockMove(idx, 1)"
              @create-below="onCreateBelow(idx)"
              @insert-above="onInsertAt(idx)"
              @insert-below="onInsertAt(idx + 1)"
            />

            <!-- Add Block Button -->
            <div class="relative mt-3" ref="addBlockRef">
              <button
                v-if="page"
                class="w-full py-3 text-sm text-slate-400 hover:text-slate-600 hover:bg-slate-50 rounded-xl transition-all border border-dashed border-slate-200 flex items-center justify-center gap-2"
                @click="toggleAddBlock"
              >
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                添加内容
              </button>
              <Teleport to="body">
                <div v-if="showAddBlock" class="fixed inset-0 z-40" @click="showAddBlock = false" />
                <div v-if="showAddBlock" ref="addBlockPopup" class="fixed z-50 w-64 bg-white rounded-xl shadow-lg border border-slate-200 py-1" :style="addBlockStyle" @click.stop>
                  <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">基础块</div>
                  <button v-for="bt in baseBlocks" :key="bt.type" class="block-menu-item" @click="addBlock(bt.type, bt.default)">
                    <span class="w-8 h-8 flex items-center justify-center bg-slate-50 rounded-lg text-lg">{{ bt.icon }}</span>
                    <div class="flex-1 text-left">
                      <div class="text-sm font-medium">{{ bt.label }}</div>
                      <div class="text-[10px] text-slate-400">{{ bt.shortcut }}</div>
                    </div>
                  </button>
                  <div class="my-1 border-t border-slate-100" />
                  <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">媒体与嵌入</div>
                  <button v-for="bt in mediaBlocks" :key="bt.type" class="block-menu-item" @click="addBlock(bt.type, bt.default)">
                    <span class="w-8 h-8 flex items-center justify-center bg-slate-50 rounded-lg text-lg">{{ bt.icon }}</span>
                    <div class="flex-1 text-left">
                      <div class="text-sm font-medium">{{ bt.label }}</div>
                      <div class="text-[10px] text-slate-400">{{ bt.shortcut }}</div>
                    </div>
                  </button>
                </div>
              </Teleport>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== TOC Sidebar ===== -->
      <aside
        v-if="pageSettings.showToc && page && headingTree.length > 0"
        class="shrink-0 overflow-y-auto border-l border-slate-100 bg-white relative"
        :style="{ width: tocWidth + 'px' }"
      >
        <div
          class="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-brand-400/30 transition-colors group/resize z-10"
          @mousedown="onTocResizeStart"
        >
          <div class="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-8 bg-slate-200 group-hover/resize:bg-brand-400 transition-colors rounded" />
        </div>
        <div class="px-3 py-4">
          <h4 class="text-xs font-semibold text-slate-400 mb-3 px-1">TOC</h4>
          <nav class="space-y-0">
            <div v-for="(node, idx) in visibleHeadings" :key="node.blockId">
              <div
                class="flex items-center group/toc rounded hover:bg-slate-50 transition-colors cursor-pointer"
                :style="{ paddingLeft: `${(node.level - minHeadingLevel) * 12 + 4}px` }"
                @click="scrollToBlock(node.blockId)"
              >
                <button
                  v-if="node.children.length > 0"
                  class="w-5 h-5 shrink-0 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors rounded"
                  @click.stop="toggleCollapse(node.blockId)"
                >
                  <svg class="w-3 h-3 transition-transform" :class="collapsedMap[node.blockId] ? '' : 'rotate-90'" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7" /></svg>
                </button>
                <span v-else class="w-5 h-5 shrink-0" />
                <span
                  class="text-sm py-1 truncate flex-1"
                  :class="node.level === minHeadingLevel ? 'font-semibold text-slate-700' : 'text-slate-500 hover:text-slate-700'"
                  :title="node.text"
                >
                  <span v-if="pageSettings.autoNumbering" class="text-slate-400 mr-1 font-mono text-[0.8em]">{{ node.number }}</span>
                  {{ node.text }}
                </span>
              </div>
            </div>
          </nav>
        </div>
      </aside>
    </div>

    <!-- ===== ICON PICKER MODAL ===== -->
    <Teleport to="body">
      <div v-if="showIconPicker" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="showIconPicker = false">
        <div class="bg-white rounded-2xl p-6 w-[420px] shadow-xl max-h-[80vh] flex flex-col">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-slate-800">选择图标</h3>
            <button class="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 text-slate-400" @click="showIconPicker = false">
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          </div>
          <!-- Search -->
          <div class="relative mb-3">
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            <input
              v-model="iconSearchText"
              class="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500"
              placeholder="搜索图标..."
              @keydown.escape="showIconPicker = false"
            />
          </div>
          <!-- Icon Grid -->
          <div class="flex-1 overflow-y-auto">
            <div class="grid grid-cols-4 gap-2">
              <button
                v-for="icon in filteredIconLibrary"
                :key="icon.id"
                class="flex flex-col items-center gap-1 p-3 rounded-xl transition-all hover:bg-slate-100"
                :class="{ 'ring-2 ring-brand-500 bg-brand-50': page?.icon === icon.id }"
                :title="icon.label"
                @click="selectIcon(icon.id)"
              >
                <div class="w-8 h-8 flex items-center justify-center text-slate-600">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-7 h-7">
                    <path v-for="(p, pi) in icon.paths" :key="pi" :d="p.d" :fill="p.fill || undefined" :stroke-width="p.strokeWidth || undefined" />
                  </svg>
                </div>
                <span class="text-[10px] text-slate-500 leading-tight text-center">{{ icon.label }}</span>
              </button>
            </div>
            <div v-if="filteredIconLibrary.length === 0" class="py-8 text-center text-sm text-slate-400">没有匹配的图标</div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ===== Settings Panel ===== -->
    <PageSettingsPanel
      :visible="showSettingsPanel"
      :page="page"
      @close="showSettingsPanel = false"
      @update-settings="onSettingsUpdate"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { usePageStore } from '@/stores/page'
import { pagesApi } from '@/api/pages'
import type { PageTreeNode, Block } from '@/types'
import BlockRenderer from './BlockRenderer.vue'
import PageSettingsPanel from './PageSettingsPanel.vue'
import type { PageSettings } from './PageSettingsPanel.vue'

const emit = defineEmits<{ navigate: [id: number]; toggleSidebar: []; pageAction: [type: string] }>()

const pageStore = usePageStore()
const router = useRouter()
const page = computed(() => pageStore.currentPage)

// ===== SVG ICON LIBRARY =====
interface IconDef { id: string; label: string; paths: { d: string; fill?: string; strokeWidth?: string }[] }

const iconLibrary: IconDef[] = [
  { id: 'doc', label: 'Document', paths: [
    { d: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z' },
    { d: 'M14 2v6h6' },
    { d: 'M16 13H8' }, { d: 'M16 17H8' }, { d: 'M10 9H8' },
  ]},
  { id: 'note', label: 'Note', paths: [
    { d: 'M11 5H6a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-7' },
    { d: 'M18.375 2.625a2.121 2.121 0 113 3L12 15l-4 1 1-4 9.375-9.375z' },
  ]},
  { id: 'star', label: 'Star', paths: [
    { d: 'M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.563 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z' },
  ]},
  { id: 'code', label: 'Code', paths: [
    { d: 'M16 18l6-6-6-6' }, { d: 'M8 6l-6 6 6 6' },
  ]},
  { id: 'book', label: 'Book', paths: [
    { d: 'M4 19.5A2.5 2.5 0 016.5 17H20' },
    { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' },
  ]},
  { id: 'gear', label: 'Settings', paths: [
    { d: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z' },
    { d: 'M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
  ]},
  { id: 'chart', label: 'Chart', paths: [
    { d: 'M3 3v18h18' },
    { d: 'M7 16l4-8 4 4 4-6' },
  ]},
  { id: 'folder', label: 'Folder', paths: [
    { d: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6.465a1 1 0 01-.832-.445l-1.11-1.664A2 2 0 009.535 4H5a2 2 0 00-2 2z' },
  ]},
  { id: 'lightbulb', label: 'Idea', paths: [
    { d: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a1 1 0 01-1 1h-2a1 1 0 01-1-1v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' },
  ]},
  { id: 'pin', label: 'Pin', paths: [
    { d: 'M15 10.5a3 3 0 11-6 0 3 3 0 016 0z' },
    { d: 'M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 0115 0z' },
  ]},
  { id: 'target', label: 'Target', paths: [
    { d: 'M12 12m-1 0a1 1 0 102 0 1 1 0 10-2 0' },
    { d: 'M12 12m-5 0a5 5 0 1010 0 5 5 0 10-10 0' },
    { d: 'M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0' },
  ]},
  { id: 'rocket', label: 'Rocket', paths: [
    { d: 'M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z' },
    { d: 'M12 15l-3-3a22 22 0 012.133-6.009A8.5 8.5 0 0115 4.357M15 4.357A8.5 8.5 0 0121 3a8.5 8.5 0 01-1.357 6A22 22 0 0115 12' },
    { d: 'M9 15l-5 5' }, { d: 'M15 9l5-5' },
  ]},
  { id: 'shield', label: 'Shield', paths: [
    { d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' },
    { d: 'M9 12l2 2 4-4' },
  ]},
  { id: 'database', label: 'Database', paths: [
    { d: 'M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3' },
    { d: 'M4 7v6c0 1.657 3.582 3 8 3s8-1.343 8-3V7' },
    { d: 'M4 7v6c0 1.657 3.582 3 8 3s8-1.343 8-3' },
  ]},
  { id: 'cloud', label: 'Cloud', paths: [
    { d: 'M17.5 19H9a7 7 0 116.71-9h1.79a4.5 4.5 0 110 9z' },
  ]},
  { id: 'heart', label: 'Heart', paths: [
    { d: 'M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z' },
  ]},
]

const iconMap = new Map(iconLibrary.map(i => [i.id, i]))

function getPageIconPaths(iconValue: string | null | undefined): IconDef['paths'] | null {
  if (!iconValue) return null
  const def = iconMap.get(iconValue)
  return def ? def.paths : null
}

// Breadcrumbs
const breadcrumbs = computed(() => {
  if (!page.value) return []
  return pageStore.getBreadcrumb(page.value.id)
})

function onNavigateBreadcrumb(crumb: { id: number; slug: string }) {
  emit('navigate', crumb.id)
}

// Flatten page tree for page_link blocks
function flattenTree(nodes: PageTreeNode[]): PageTreeNode[] {
  const result: PageTreeNode[] = []
  function walk(list: PageTreeNode[]) {
    for (const n of list) {
      result.push(n)
      if (n.children) walk(n.children)
      if (n.linked_children) walk(n.linked_children)
    }
  }
  walk(nodes)
  return result
}
const flatPages = computed(() => flattenTree(pageStore.tree))

// ===== Title Editing =====
const pageTitle = ref('')

watch(() => page.value?.title, (t) => {
  if (t !== undefined) pageTitle.value = t
}, { immediate: true })

async function savePageTitle() {
  if (!page.value) return
  const title = pageTitle.value.trim() || '无标题'
  if (title !== page.value.title) {
    await pagesApi.update(page.value.id, { title })
    page.value.title = title
    await pageStore.fetchTree()
  }
}

// ===== Icon Picker =====
const showIconPicker = ref(false)
const iconSearchText = ref('')

const filteredIconLibrary = computed(() => {
  const q = iconSearchText.value.toLowerCase().trim()
  if (!q) return iconLibrary
  return iconLibrary.filter(icon =>
    icon.label.toLowerCase().includes(q) || icon.id.toLowerCase().includes(q)
  )
})

function openIconPicker() {
  iconSearchText.value = ''
  showIconPicker.value = true
}

async function selectIcon(iconId: string) {
  showIconPicker.value = false
  if (!page.value || page.value.icon === iconId) return
  await pagesApi.update(page.value.id, { icon: iconId })
  page.value.icon = iconId
}

// ===== Content Placeholder Logic =====
function isBlockEmpty(b: Block): boolean {
  const c = b.content
  if (b.type === 'paragraph' || b.type === 'heading' || b.type === 'quote' || b.type === 'callout') {
    return !(c.text as string)?.trim()
  }
  if (b.type === 'code') return !(c.code as string)?.trim()
  if (b.type === 'list') {
    const items = c.items as Array<{ text?: string }> | undefined
    return !items?.some(item => (item.text || '')?.trim())
  }
  if (b.type === 'image') return !(c.url as string)?.trim()
  if (b.type === 'table') return !((c.headers as string[])?.length)
  // divider, page_link are always "content"
  if (b.type === 'divider' || b.type === 'page_link') return false
  return true
}

const allBlocksEmpty = computed(() => {
  if (!page.value?.blocks || page.value.blocks.length === 0) return true
  return page.value.blocks.every(b => isBlockEmpty(b))
})

// ===== TOC Tree =====
interface TocNode {
  blockId: number
  level: number
  text: string
  number: string
  children: TocNode[]
}

const headingTree = computed<TocNode[]>(() => {
  if (!page.value?.blocks) return []
  const root: TocNode[] = []
  const stack: TocNode[] = []
  const counters = [0, 0, 0, 0, 0, 0]

  for (const block of page.value.blocks) {
    if (block.type !== 'heading') continue
    const level = Number((block.content as Record<string, unknown>).level) || 1
    if (level < 1 || level > 6) continue
    const text = String((block.content as Record<string, unknown>).text || '').trim()
    if (!text) continue

    counters[level - 1]++
    for (let l = level; l < 6; l++) counters[l] = 0
    const number = counters.slice(0, level).join('.')

    const node: TocNode = { blockId: block.id, level, text, number, children: [] }
    while (stack.length > 0 && stack[stack.length - 1].level >= level) {
      stack.pop()
    }
    if (stack.length > 0) {
      stack[stack.length - 1].children.push(node)
    } else {
      root.push(node)
    }
    stack.push(node)
  }
  return root
})

const minHeadingLevel = computed(() => {
  if (headingTree.value.length === 0) return 1
  let min = 6
  for (const node of headingTree.value) {
    min = Math.min(min, node.level)
  }
  return min
})

const collapsedMap = ref<Record<number, boolean>>({})

watch(headingTree, (tree) => {
  const map: Record<number, boolean> = {}
  const initCollapse = (nodes: TocNode[], depthFromMin: number) => {
    for (const node of nodes) {
      map[node.blockId] = depthFromMin >= 2
      initCollapse(node.children, depthFromMin + 1)
    }
  }
  initCollapse(tree, 0)
  collapsedMap.value = map
}, { immediate: true })

const visibleHeadings = computed<TocNode[]>(() => {
  const result: TocNode[] = []
  const walk = (nodes: TocNode[]) => {
    for (const node of nodes) {
      result.push(node)
      if (!collapsedMap.value[node.blockId]) {
        walk(node.children)
      }
    }
  }
  walk(headingTree.value)
  return result
})

function toggleCollapse(blockId: number) {
  collapsedMap.value = { ...collapsedMap.value, [blockId]: !collapsedMap.value[blockId] }
}

const headingNumbers = computed(() => {
  const map = new Map<number, string>()
  if (!page.value?.blocks) return map
  const counters = [0, 0, 0, 0, 0, 0]
  for (const block of page.value.blocks) {
    if (block.type !== 'heading') continue
    const level = Number((block.content as Record<string, unknown>).level) || 1
    if (level < 1 || level > 6) continue
    counters[level - 1]++
    for (let l = level; l < 6; l++) counters[l] = 0
    map.set(block.id, counters.slice(0, level).join('.'))
  }
  return map
})

// ===== Page Settings =====
const showSettingsPanel = ref(false)
const contentAreaStyle = computed(() => {
  if (showSettingsPanel.value) return { marginRight: '320px' }
  return {}
})

const tocWidth = ref(224)
const MIN_TOC_WIDTH = 150
const MAX_TOC_WIDTH_RATIO = 0.4

function onTocResizeStart(e: MouseEvent) {
  const startX = e.clientX
  const startWidth = tocWidth.value
  const contentArea = contentAreaRef.value
  const maxWidth = contentArea ? contentArea.clientWidth * MAX_TOC_WIDTH_RATIO : 500

  function onMove(ev: MouseEvent) {
    const delta = startX - ev.clientX
    tocWidth.value = Math.max(MIN_TOC_WIDTH, Math.min(maxWidth, startWidth + delta))
  }
  function onUp() {
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
}

const pageSettings = ref<PageSettings>({
  adaptiveWidth: false,
  smallFont: false,
  showToc: false,
  autoNumbering: false,
})
const contentAreaRef = ref<HTMLElement>()

function loadPageSettings() {
  try {
    const raw = localStorage.getItem('page-settings')
    if (raw) {
      pageSettings.value = { ...pageSettings.value, ...JSON.parse(raw) }
    }
  } catch { /* ignore */ }
}
loadPageSettings()

function onSettingsUpdate(settings: PageSettings) {
  pageSettings.value = { ...settings }
}

function scrollToBlock(blockId: number) {
  const container = contentAreaRef.value
  if (!container) return
  const el = container.querySelector(`[data-block-id="${blockId}"]`)
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

async function togglePin() {
  if (!page.value) return
  await pageStore.updatePage(page.value.id, { is_pinned: !page.value.is_pinned })
}

// ===== Block Operations =====
const showAddBlock = ref(false)
const addBlockRef = ref<HTMLElement>()
const addBlockStyle = ref<Record<string, string>>({})
const addBlockPopup = ref<HTMLElement>()

const baseBlocks = [
  { type: 'paragraph', label: '段落', icon: 'P', shortcut: '输入文本', default: { text: '' } },
  { type: 'heading', label: '一级标题', icon: 'H1', shortcut: '# 空格 / Ctrl+1', default: { level: 1, text: '' } },
  { type: 'heading', label: '二级标题', icon: 'H2', shortcut: '## 空格 / Ctrl+2', default: { level: 2, text: '' } },
  { type: 'heading', label: '三级标题', icon: 'H3', shortcut: '### 空格 / Ctrl+3', default: { level: 3, text: '' } },
  { type: 'list', label: '无序列表', icon: '•', shortcut: '- 空格', default: { ordered: false, items: [] } },
  { type: 'list', label: '有序列表', icon: '1.', shortcut: '1. 空格', default: { ordered: true, items: [] } },
  { type: 'list', label: '任务列表', icon: '☑', shortcut: '- [ ] 空格', default: { ordered: false, task: true, items: [] } },
  { type: 'quote', label: '引用', icon: '❝', shortcut: '> 空格', default: { text: '' } },
  { type: 'divider', label: '分割线', icon: '—', shortcut: '---', default: {} },
  { type: 'table', label: '表格', icon: '▦', shortcut: '| 列1 | 列2 |', default: { headers: ['列1', '列2'], rows: [] } },
  { type: 'code', label: '代码块', icon: '</>', shortcut: '``` 语言 / Ctrl+Shift+K', default: { language: 'python', code: '' } },
  { type: 'callout', label: '高亮块', icon: '\uD83D\uDCA1', shortcut: '', default: { type: 'info', text: '高亮块内容' } },
]
const mediaBlocks = [
  { type: 'page_link', label: '页面链接', icon: '\uD83D\uDD17', shortcut: '', default: { page_id: 0, title: '' } },
  { type: 'image', label: '图片', icon: '\uD83D\uDDBC\uFE0F', shortcut: '', default: { url: '', alt: '' } },
]

function toggleAddBlock(e: MouseEvent) {
  showAddBlock.value = !showAddBlock.value
  if (!showAddBlock.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  addBlockStyle.value = { top: `${rect.top - 200}px`, left: `${rect.left}px` }
}

watch(showAddBlock, (v) => {
  if (v && addBlockRef.value) {
    const rect = addBlockRef.value.getBoundingClientRect()
    const vw = window.innerWidth
    const estimatedHeight = 430
    let top = rect.top - estimatedHeight
    if (top < 60) top = rect.bottom + 4
    let left = rect.left
    if (left + 256 > vw - 8) left = Math.max(4, vw - 256 - 8)
    addBlockStyle.value = { top: `${Math.max(4, top)}px`, left: `${left}px` }
    nextTick(() => {
      const popup = addBlockPopup.value
      if (!popup) return
      const popupRect = popup.getBoundingClientRect()
      let newTop: string | undefined
      let newLeft: string | undefined
      if (popupRect.bottom > window.innerHeight - 8) {
        newTop = `${Math.max(4, rect.top - popupRect.height - 4)}px`
      }
      if (popupRect.right > window.innerWidth - 8) {
        newLeft = `${Math.max(4, window.innerWidth - popupRect.width - 8)}px`
      }
      if (newTop || newLeft) {
        addBlockStyle.value = {
          ...addBlockStyle.value,
          ...(newTop ? { top: newTop } : {}),
          ...(newLeft ? { left: newLeft } : {}),
        }
      }
    })
  }
})

async function addBlock(type: string, content: Record<string, unknown>) {
  if (!page.value) return
  showAddBlock.value = false
  await pageStore.addBlock(page.value.id, type, content)
}

async function onBlockSave(blockId: number, content: Record<string, unknown>) {
  await pageStore.updateBlock(blockId, { content })
}

async function onChangeBlockType(blockId: number, newType: string) {
  await pageStore.updateBlock(blockId, { type: newType })
}
async function onBlockDelete(blockId: number) {
  await pageStore.deleteBlock(blockId)
}
async function onBlockDuplicate(blockId: number) {
  await pageStore.duplicateBlock(blockId)
}
async function onBlockMove(idx: number, delta: number) {
  if (!page.value) return
  const newIdx = idx + delta
  if (newIdx < 0 || newIdx >= page.value.blocks.length) return
  const ids = page.value.blocks.map(b => b.id)
  const temp = ids[idx]; ids[idx] = ids[newIdx]; ids[newIdx] = temp
  await pageStore.reorderBlocks(page.value.id, ids)
}
async function onCreateBelow(idx: number) {
  if (!page.value) return
  const newBlock = await pageStore.insertBlockAt(page.value.id, idx + 1, 'paragraph', { text: '' })
  const ids = page.value.blocks.map(b => b.id)
  await pageStore.reorderBlocks(page.value.id, ids)
  await nextTick()
  const el = contentAreaRef.value?.querySelector(`[data-block-id="${newBlock.id}"] textarea, [data-block-id="${newBlock.id}"] input`)
  if (el instanceof HTMLElement) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.focus()
  }
}
async function onInsertAt(idx: number) {
  if (!page.value) return
  const insertIdx = Math.max(0, Math.min(idx, page.value.blocks.length))
  const newBlock = await pageStore.insertBlockAt(page.value.id, insertIdx, 'paragraph', { text: '' })
  const ids = page.value.blocks.map(b => b.id)
  await pageStore.reorderBlocks(page.value.id, ids)
  await nextTick()
  const el = contentAreaRef.value?.querySelector(`[data-block-id="${newBlock.id}"] textarea, [data-block-id="${newBlock.id}"] input`)
  if (el instanceof HTMLElement) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    el.focus()
  }
}
async function onMoveTo(fromIdx: number, toIdx: number, position: 'above' | 'below' = 'below') {
  if (!page.value || fromIdx === toIdx) return
  const ids = page.value.blocks.map(b => b.id)
  const moved = ids.splice(fromIdx, 1)[0]
  let insertAt: number
  if (position === 'below') {
    insertAt = fromIdx < toIdx ? toIdx : toIdx + 1
  } else {
    insertAt = fromIdx < toIdx ? toIdx - 1 : toIdx
  }
  ids.splice(insertAt, 0, moved)
  await pageStore.reorderBlocks(page.value.id, ids)
}
</script>

<style scoped>
.page-menu-item {
  @apply w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors text-left;
}
.block-menu-item {
  @apply w-full flex items-center gap-3 px-3 py-2 hover:bg-slate-50 transition-colors text-left;
}
</style>
