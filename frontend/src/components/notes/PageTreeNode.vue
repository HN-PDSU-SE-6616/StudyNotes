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
      <!-- 批量模式勾选框 -->
      <span
        v-if="batchOpen"
        class="w-4 h-4 shrink-0 rounded border-2 flex items-center justify-center transition-colors"
        :class="isChecked ? 'bg-brand-500 border-brand-500 text-white' : 'border-slate-300 bg-white'"
      >
        <svg v-if="isChecked" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3.5" d="M5 13l4 4L19 7" /></svg>
      </span>
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
      <!-- Icon: render SVG if in library, else emoji/text -->
      <span v-if="getIconPaths(node.icon)" class="shrink-0 w-4 h-4 text-slate-500">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4">
          <path v-for="(p, pi) in getIconPaths(node.icon)!" :key="pi" :d="p.d" :fill="p.fill || undefined" :stroke-width="p.strokeWidth || undefined" />
        </svg>
      </span>
      <span v-else class="shrink-0">{{ node.icon || '📄' }}</span>

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
            <button class="menu-item w-full justify-between" @click="openPopup('move')">
              <span class="flex items-center gap-2.5">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 7.5L7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5" /></svg>
                <span>移动到</span>
              </span>
              <svg class="w-3 h-3 text-slate-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
            </button>

            <!-- 嵌入到 -->
            <button class="menu-item w-full justify-between" @click="openPopup('embed')">
              <span class="flex items-center gap-2.5">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15a2.25 2.25 0 012.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z" /></svg>
                <span>嵌入到</span>
              </span>
              <svg class="w-3 h-3 text-slate-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
            </button>

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

            <!-- 新建页面 -->
            <button class="menu-item" @click="action('addSubPage')">
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v6m3-3H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <span>新建页面</span>
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

        <!-- 选择目标页面弹窗（独立 Teleport，不受 menuOpen 影响）-->
        <Teleport to="body">
          <div v-if="pageSelectOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="closePopup">
            <div class="bg-white rounded-2xl p-5 w-[440px] shadow-xl max-h-[75vh] flex flex-col">
              <h3 class="text-base font-semibold text-slate-800 mb-3">{{ popupMode === 'move' ? '移动到' : '嵌入到' }}</h3>
              <div class="relative mb-3">
                <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                <input v-model="pageSearch" class="w-full pl-9 pr-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500" placeholder="搜索页面..." />
              </div>
              <div class="flex-1 overflow-y-auto -mx-1">
                <!-- 搜索模式：扁平列表 -->
                <template v-if="pageSearch.trim()">
                  <button v-for="p in popupTreeFlat" :key="p.id" class="popup-tree-item" :style="{ paddingLeft: `${p.depth * 16 + 8}px` }" @click="selectPopupPage(p.id)">
                    <span class="shrink-0 w-4 text-center">{{ p.icon || '📄' }}</span>
                    <span class="truncate text-sm">{{ p.title }}</span>
                  </button>
                  <div v-if="popupTreeFlat.length === 0" class="py-8 text-center text-sm text-slate-400">没有匹配的页面</div>
                </template>
                <!-- 树模式 -->
                <template v-else>
                  <template v-for="p in popupTreeVisible" :key="p.id">
                    <button
                      class="popup-tree-item"
                      :style="{ paddingLeft: `${p.depth * 16 + 8}px` }"
                      @click="selectPopupPage(p.id)"
                    >
                      <button
                        v-if="p.hasChildren"
                        class="w-4 h-4 flex items-center justify-center text-slate-400 hover:text-slate-600 shrink-0 rounded"
                        @click.stop="togglePopupCollapse(p.id)"
                      >
                        <svg class="w-3 h-3 transition-transform" :class="popupCollapsed.has(p.id) ? '' : 'rotate-90'" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7" /></svg>
                      </button>
                      <span v-else class="w-4 shrink-0" />
                      <span class="shrink-0">{{ p.icon || '📄' }}</span>
                      <span class="truncate text-sm">{{ p.title }}</span>
                    </button>
                  </template>
                </template>
              </div>
              <div class="flex justify-end gap-2 mt-3 pt-3 border-t border-slate-100">
                <button class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl transition-colors" @click="closePopup">取消</button>
              </div>
            </div>
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
        :batch-open="batchOpen"
        :checked-ids="checkedIds"
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
        :batch-open="batchOpen"
        :checked-ids="checkedIds"
        @select="$emit('select', $event)"
        @action="(type, payload) => $emit('action', type, payload)"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import type { PageTreeNode as TreeNode } from '@/types'

// Shared SVG icon library (kept in sync with PageEditor)
interface IconPaths { d: string; fill?: string; strokeWidth?: string }
const iconLibPaths: Record<string, IconPaths[]> = {
  doc: [{ d: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z' }, { d: 'M14 2v6h6' }, { d: 'M16 13H8' }, { d: 'M16 17H8' }, { d: 'M10 9H8' }],
  note: [{ d: 'M11 5H6a2 2 0 00-2 2v12a2 2 0 002 2h12a2 2 0 002-2v-7' }, { d: 'M18.375 2.625a2.121 2.121 0 113 3L12 15l-4 1 1-4 9.375-9.375z' }],
  star: [{ d: 'M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z' }],
  code: [{ d: 'M16 18l6-6-6-6' }, { d: 'M8 6l-6 6 6 6' }],
  book: [{ d: 'M4 19.5A2.5 2.5 0 016.5 17H20' }, { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' }],
  gear: [{ d: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z' }, { d: 'M15 12a3 3 0 11-6 0 3 3 0 016 0z' }],
  chart: [{ d: 'M3 3v18h18' }, { d: 'M7 16l4-8 4 4 4-6' }],
  folder: [{ d: 'M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6.465a1 1 0 01-.832-.445l-1.11-1.664A2 2 0 009.535 4H5a2 2 0 00-2 2z' }],
  lightbulb: [{ d: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a1 1 0 01-1 1h-2a1 1 0 01-1-1v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' }],
  pin: [{ d: 'M15 10.5a3 3 0 11-6 0 3 3 0 016 0z' }, { d: 'M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 0115 0z' }],
  target: [{ d: 'M12 12m-1 0a1 1 0 102 0 1 1 0 10-2 0' }, { d: 'M12 12m-5 0a5 5 0 1010 0 5 5 0 10-10 0' }, { d: 'M12 12m-9 0a9 9 0 1018 0 9 9 0 10-18 0' }],
  rocket: [{ d: 'M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 00-2.91-.09z' }, { d: 'M12 15l-3-3a22 22 0 012.133-6.009A8.5 8.5 0 0115 4.357M15 4.357A8.5 8.5 0 0121 3a8.5 8.5 0 01-1.357 6A22 22 0 0115 12' }, { d: 'M9 15l-5 5' }, { d: 'M15 9l5-5' }],
  shield: [{ d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' }, { d: 'M9 12l2 2 4-4' }],
  database: [{ d: 'M4 7c0-1.657 3.582-3 8-3s8 1.343 8 3' }, { d: 'M4 7v6c0 1.657 3.582 3 8 3s8-1.343 8-3V7' }, { d: 'M4 7v6c0 1.657 3.582 3 8 3s8-1.343 8-3' }],
  cloud: [{ d: 'M17.5 19H9a7 7 0 116.71-9h1.79a4.5 4.5 0 110 9z' }],
  heart: [{ d: 'M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z' }],
}
function getIconPaths(iconValue: string | null | undefined): IconPaths[] | null {
  if (!iconValue) return null
  return iconLibPaths[iconValue] || null
}

const props = defineProps<{
  node: TreeNode
  activeId?: number | null
  depth?: number
  isLinked?: boolean
  allPages?: TreeNode[]
  batchOpen?: boolean
  checkedIds?: string[]
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
const isChecked = computed(() => (props.checkedIds || []).includes(String(props.node.id)))
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
}

// 弹窗状态（移动到/嵌入到）
const pageSelectOpen = ref(false)
const popupMode = ref<'move' | 'embed'>('move')
const pageSearch = ref('')
const popupCollapsed = ref(new Set<number>())  // 弹窗树中折叠的节点ID

interface FlatTreeNode { id: number; title: string; icon?: string | null; depth: number; hasChildren: boolean }

/** 将树展平为带深度的列表，支持折叠 */
function flattenPopupTree(nodes: TreeNode[], depth: number, collapsed: Set<number>, out: FlatTreeNode[]) {
  for (const n of nodes) {
    const hasChildren = (n.children?.length ?? 0) + (n.linked_children?.length ?? 0) > 0
    out.push({ id: n.id, title: n.title, icon: n.icon, depth, hasChildren })
    if (!collapsed.has(n.id)) {
      if (n.children) flattenPopupTree(n.children, depth + 1, collapsed, out)
      if (n.linked_children) flattenPopupTree(n.linked_children, depth + 1, collapsed, out)
    }
  }
}

/** 树模式下可展开的扁平列表 */
const popupTreeVisible = computed(() => {
  const out: FlatTreeNode[] = []
  flattenPopupTree(props.allPages || [], 0, popupCollapsed.value, out)
  return out
})

/** 搜索模式下匹配的扁平列表 */
const popupTreeFlat = computed(() => {
  const q = pageSearch.value.toLowerCase().trim()
  if (!q) return []
  return popupTreeVisible.value.filter(p => p.title.toLowerCase().includes(q))
})

function togglePopupCollapse(nodeId: number) {
  const next = new Set(popupCollapsed.value)
  if (next.has(nodeId)) next.delete(nodeId)
  else next.add(nodeId)
  popupCollapsed.value = next
}

function openPopup(mode: 'move' | 'embed') {
  closeMenu()
  popupMode.value = mode
  pageSearch.value = ''
  popupCollapsed.value = new Set()  // 默认全部展开
  pageSelectOpen.value = true
}

function closePopup() {
  pageSelectOpen.value = false
}

function selectPopupPage(targetId: number) {
  closePopup()
  if (popupMode.value === 'move') {
    emit('action', 'move', { pageId: props.node.id, parentId: targetId, title: props.node.title })
  } else {
    emit('action', 'embed', { pageId: props.node.id, targetId })
  }
}

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

async function action(type: string, targetId?: number | null, position?: string) {
  closeMenu()
  switch (type) {
    case 'open':
      emit('select', props.node.id)
      break
    case 'move':
      emit('action', 'move', { pageId: props.node.id, parentId: targetId ?? null, title: props.node.title })
      break
    case 'embed':
      emit('action', 'embed', { pageId: props.node.id, targetId, position: position || 'bottom' })
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

.popup-tree-item {
  @apply w-full flex items-center gap-1.5 px-2 py-1.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors text-left rounded;
}

.sub-menu {
  @apply absolute left-full top-0 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1 ml-1 max-h-48 overflow-y-auto;
}
</style>
