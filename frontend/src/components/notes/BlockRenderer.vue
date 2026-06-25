<template>
  <div
    class="block-item group relative flex gap-2 transition-all duration-150 mb-2"
    :class="{
      'bg-slate-50/50 -mx-4 px-4 rounded-lg': showHandle,
      'opacity-30': isDragging,
      'border-t-2 border-brand-400': dragOverPosition === 'above',
      'border-b-2 border-brand-400': dragOverPosition === 'below',
    }"
    :data-block-id="block.id"
    @mouseenter="showHandle = true"
    @mouseleave="onMouseLeave"
    @contextmenu.prevent="onContextMenu"
    @dragover.prevent="onDragOver"
    @dragleave="onDragLeave"
    @drop.prevent="onDrop"
  >
    <!-- ===== 左侧拖拽手柄 + 操作按钮 ===== -->
    <div
      class="relative shrink-0 self-start w-6 h-6 mt-1.5"
      :class="{ 'opacity-0 group-hover:opacity-100': !blockMenuOpen && !isDragging }"
      :style="{ opacity: blockMenuOpen || isDragging ? 1 : undefined }"
      @mousemove="onHandleMouseMove"
      @mouseleave="onHandleMouseLeave"
    >
      <!-- 上方插入按钮 -->
      <button
        class="block-insert-btn"
        :class="{ 'opacity-100': showTopInsert, 'opacity-0': !showTopInsert }"
        style="top: -14px"
        title="在上方插入"
        @click.stop="$emit('insertAbove')"
      >
        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M12 4v16m8-8H4" /></svg>
      </button>

      <!-- 拖拽手柄 -->
      <button
        class="absolute inset-0 w-full h-full flex items-center justify-center rounded text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors cursor-grab active:cursor-grabbing"
        :class="{ 'text-brand-500 bg-brand-50': isDragging }"
        title="拖拽移动 / 点击查看选项"
        draggable="true"
        @click.stop="toggleBlockMenu"
        @dragstart="onDragStart"
        @dragend="onDragEnd"
      >
        <svg class="w-4 h-4 pointer-events-none" fill="currentColor" viewBox="0 0 20 20"><path d="M7 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 2a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 8a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM7 14a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM13 14a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>
      </button>

      <!-- 下方插入按钮 -->
      <button
        class="block-insert-btn"
        :class="{ 'opacity-100': showBottomInsert, 'opacity-0': !showBottomInsert }"
        style="bottom: -14px"
        title="在下方插入"
        @click.stop="$emit('insertBelow')"
      >
        <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M12 4v16m8-8H4" /></svg>
      </button>

      <!-- Block 操作下拉菜单 -->
      <Teleport to="body">
        <div v-if="blockMenuOpen" class="fixed inset-0 z-40" @click="blockMenuOpen = false" />
        <div v-if="blockMenuOpen" ref="blockMenuPopup" class="fixed z-50 w-56 bg-white rounded-xl shadow-lg border border-slate-200 py-1 max-h-[70vh] overflow-y-auto" :style="blockMenuStyle" @click.stop>
          <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">转换类型</div>
          <button v-for="bt in typeOptions" :key="bt.type" class="block-menu-item" @click="changeType(bt.type)">
            <span class="w-5 text-center">{{ bt.icon }}</span><span>{{ bt.label }}</span>
          </button>
          <div class="my-0.5 border-t border-slate-100" />
          <!-- 标题级别（右侧展开）-->
          <div ref="headingSubTrigger" class="relative" @mouseenter="openHeadingSubMenu" @mouseleave="scheduleHideHeadingSub">
            <button class="block-menu-item w-full justify-between">
              <span class="w-5 text-center text-xs font-mono text-slate-400">H</span><span>标题级别</span>
              <svg class="w-3 h-3 text-slate-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
            </button>
          </div>
          <!-- 列表类型（右侧展开）-->
          <div ref="listSubTrigger" class="relative" @mouseenter="openListSubMenu" @mouseleave="scheduleHideListSub">
            <button class="block-menu-item w-full justify-between">
              <span class="w-5 text-center">•</span><span>列表类型</span>
              <svg class="w-3 h-3 text-slate-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
            </button>
          </div>
          <!-- Teleport 子菜单 -->
          <Teleport to="body">
            <div v-if="showHeadingSubMenu" class="fixed z-[60] w-40 bg-white rounded-xl shadow-lg border border-slate-200 py-1 max-h-48 overflow-y-auto" :style="headingSubStyle" @mouseenter="enterHeadingSubMenu" @mouseleave="showHeadingSubMenu = false">
              <button v-for="lv in [1,2,3,4,5,6]" :key="'h'+lv" class="block-menu-item" @click="quickConvertFromMenu('heading', lv)"><span class="text-xs font-mono text-slate-400 w-5">H{{ lv }}</span><span>{{ ['一级','二级','三级','四级','五级','六级'][lv-1] }}标题</span></button>
            </div>
          </Teleport>
          <Teleport to="body">
            <div v-if="showListSubMenu" class="fixed z-[60] w-40 bg-white rounded-xl shadow-lg border border-slate-200 py-1 max-h-48 overflow-y-auto" :style="listSubStyle" @mouseenter="enterListSubMenu" @mouseleave="showListSubMenu = false">
              <button class="block-menu-item" @click="quickConvertFromMenu('list', false)"><span class="w-5 text-center">•</span><span>无序列表</span></button>
              <button class="block-menu-item" @click="quickConvertFromMenu('list', true)"><span class="w-5 text-center">1.</span><span>有序列表</span></button>
              <button class="block-menu-item" @click="quickConvertFromMenu('list', false, true)"><span class="w-5 text-center">☑</span><span>任务列表</span></button>
            </div>
          </Teleport>
          <div class="my-0.5 border-t border-slate-100" />
          <button class="block-menu-item" @click="$emit('duplicate')">
            <span class="w-5 text-center">📋</span><span>拷贝副本</span>
          </button>
          <button class="block-menu-item" @click="showColorPicker = !showColorPicker">
            <span class="w-5 text-center">🎨</span><span>修改字体颜色</span>
          </button>
          <div v-if="showColorPicker" class="px-3 py-1.5">
            <div class="flex gap-1.5 flex-wrap">
              <button v-for="c in colors" :key="c" class="w-6 h-6 rounded-full border-2 border-slate-200 hover:scale-110 transition-transform" :style="{ background: c }" :title="c" @click="setTextColor(c)" />
              <button class="w-6 h-6 rounded-full border-2 border-dashed border-slate-300 flex items-center justify-center hover:scale-110 transition-transform" title="清除字体颜色" @click="setTextColor('transparent')">
                <svg class="w-3 h-3 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
          </div>
          <button class="block-menu-item" @click="toggleCenter">
            <span class="w-5 text-center">{{ isCentered ? '📐' : '📏' }}</span>
            <span>{{ isCentered ? '取消居中' : '文字居中' }}</span>
          </button>
          <div class="my-0.5 border-t border-slate-100" />
          <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">常用颜色</div>
          <div class="px-3 py-1">
            <div class="flex gap-1 flex-wrap">
              <button v-for="c in textColors" :key="c.color" class="w-6 h-6 rounded-full border-2 border-slate-200 hover:scale-110 transition-transform" :style="{ background: c.color }" :title="c.name" @click="setTextColor(c.color)" />
            </div>
          </div>
          <div class="my-0.5 border-t border-slate-100" />
          <button class="block-menu-item" @click="$emit('moveUp')">
            <span class="w-5 text-center">⬆️</span><span>上移</span>
          </button>
          <button class="block-menu-item" @click="$emit('moveDown')">
            <span class="w-5 text-center">⬇️</span><span>下移</span>
          </button>
          <div class="my-0.5 border-t border-slate-100" />
          <button class="block-menu-item text-red-600 hover:bg-red-50" @click="$emit('delete')">
            <span class="w-5 text-center">🗑️</span><span>删除</span>
          </button>
        </div>
      </Teleport>

      <!-- 右键菜单 -->
      <Teleport to="body">
        <div v-if="ctxMenuOpen" class="fixed inset-0 z-40" @click="ctxMenuOpen = false" />
        <div v-if="ctxMenuOpen" ref="ctxMenuPopup" class="fixed z-50 w-52 bg-white rounded-xl shadow-lg border border-slate-200 py-1" :style="ctxMenuStyle" @click.stop>
          <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">转换为</div>
          <button class="block-menu-item" @click="quickConvert('heading', 1)"><span class="text-xs font-mono text-slate-400 w-5">H1</span> # 一级标题</button>
          <button class="block-menu-item" @click="quickConvert('heading', 2)"><span class="text-xs font-mono text-slate-400 w-5">H2</span> ## 二级标题</button>
          <button class="block-menu-item" @click="quickConvert('heading', 3)"><span class="text-xs font-mono text-slate-400 w-5">H3</span> ### 三级标题</button>
          <button class="block-menu-item" @click="quickConvert('heading', 4)"><span class="text-xs font-mono text-slate-400 w-5">H4</span> #### 四级标题</button>
          <button class="block-menu-item" @click="quickConvert('list', false)"><span class="w-5">•</span> 无序列表</button>
          <button class="block-menu-item" @click="quickConvert('list', true)"><span class="w-5">1.</span> 有序列表</button>
          <button class="block-menu-item" @click="quickConvert('quote')"><span class="w-5">❝</span> 引用</button>
          <button class="block-menu-item" @click="quickConvert('code')"><span class="w-5">&lt;/&gt;</span> 代码块</button>
          <div class="my-0.5 border-t border-slate-100" />
          <div class="px-3 py-1.5 text-[10px] font-semibold text-slate-400 uppercase tracking-wider">操作</div>
          <button class="block-menu-item" @click="$emit('duplicate'); ctxMenuOpen = false"><span class="w-5">📋</span> 拷贝副本</button>
          <button class="block-menu-item" @click="$emit('delete'); ctxMenuOpen = false"><span class="w-5">🗑️</span> 删除</button>
        </div>
      </Teleport>
    </div>

    <!-- ===== Block 内容渲染 ===== -->
    <div class="flex-1 min-w-0" :style="blockStyle">
      <!-- 段落 -->
      <div v-if="block.type === 'paragraph'" class="py-1">
        <p
          v-if="!editing"
          class="text-slate-700 leading-relaxed cursor-text min-h-[1.5em]"
          :class="{ [placeholderClass]: !text }"
          @click="startEdit"
          v-html="formattedText || props.contentPlaceholder || ''"
        />
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none text-slate-700 leading-relaxed"
          @blur="saveEdit"
          @keydown.enter.exact="$event.preventDefault(); onEnterInEdit()"
          @keydown.escape="cancelEdit"
          @keydown="onEditKeydown"
          @paste="onPaste"
          @input="autoResize"
        />
      </div>

      <!-- 标题 -->
      <component
        v-else-if="block.type === 'heading'"
        :is="'h' + (level || 2)"
        class="font-bold text-slate-800 py-1 cursor-text group/heading"
        :class="headingClass"
        @click="startEdit"
      >
        <span v-if="!editing" :class="{ [placeholderClass]: !text }">
          <span v-if="props.settings?.autoNumbering && props.headingNumber" class="text-slate-400 mr-2 font-mono text-[0.85em]">{{ props.headingNumber }}</span>
          <span v-html="formattedText || '标题 ' + level" />
        </span>
        <input
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full bg-transparent border-none outline-none font-bold"
          @blur="saveEdit"
          @keydown.enter.prevent="onEnterInEdit"
          @keydown.escape="cancelEdit"
          @keydown="onEditKeydown"
        />
      </component>

      <!-- 代码 -->
      <div v-else-if="block.type === 'code'" class="my-2">
        <div v-if="!editing" class="cursor-pointer" @click="startEdit">
          <div class="flex items-center mb-1">
            <span class="text-[10px] font-mono text-slate-400 uppercase">{{ language || 'text' }}</span>
          </div>
          <div class="relative group/code-view">
            <pre
              class="bg-slate-900 rounded-xl p-4 pr-12 text-sm overflow-x-auto font-mono min-h-[3em]"
              :class="{ 'opacity-50': !code }"
            ><code v-if="code" class="hljs-code-block" v-html="highlightedCode" /><code v-else class="text-slate-400">点击编辑代码...</code></pre>
            <button
              v-if="code"
              class="absolute top-2 right-2 w-7 h-7 flex items-center justify-center rounded-lg bg-slate-700/60 text-slate-400 hover:text-white hover:bg-slate-600 transition-all opacity-0 group-hover/code-view:opacity-100"
              title="复制代码"
              @click.stop="copyCode"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
            </button>
          </div>
        </div>
        <div v-else class="bg-slate-900 rounded-xl">
          <div class="flex items-center gap-2 px-3 py-2 border-b border-slate-700 relative">
            <!-- 语言下拉选择器（Typora 风格：独立选项框，mousedown.prevent 防止 textarea blur） -->
            <div class="relative">
              <button
                data-code-lang-btn
                class="flex items-center gap-1 text-[10px] font-mono text-slate-400 uppercase hover:text-slate-200 transition-colors px-1.5 py-0.5 rounded hover:bg-slate-800"
                @mousedown.prevent
                @click="showLangDropdown = !showLangDropdown"
              >
                {{ editLanguage || 'text' }}
                <svg class="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M19 9l-7 7-7-7" /></svg>
              </button>
              <!-- 下拉面板：mousedown.prevent 阻止 blur，内部 click 正常触发 -->
              <Teleport to="body">
                <div v-if="showLangDropdown" class="fixed inset-0 z-40" @click="showLangDropdown = false" />
                <div
                  v-if="showLangDropdown"
                  ref="langDropdownPanel"
                  class="fixed z-50 w-56 bg-slate-800 border border-slate-600 rounded-lg shadow-2xl py-1 overflow-hidden"
                  :style="langDropdownStyle"
                  @click.stop
                  @mousedown.prevent
                >
                  <div class="px-2 pt-1 pb-1.5 border-b border-slate-600">
                    <input
                      ref="langSearchInput"
                      v-model="langSearchText"
                      class="w-full bg-slate-700 text-slate-100 text-[12px] px-2 py-1.5 rounded outline-none placeholder-slate-500"
                      placeholder="搜索语言..."
                      @keydown.escape="showLangDropdown = false; nextTick(() => inputRef?.focus())"
                      @keydown.enter.prevent="selectFirstFilteredLang"
                    />
                  </div>
                  <div class="max-h-52 overflow-y-auto py-1">
                    <button
                      v-for="opt in filteredLangOptions"
                      :key="opt.value"
                      class="w-full flex items-center justify-between px-3 py-1.5 text-[12px] transition-colors text-left"
                      :class="editLanguage === opt.value ? 'text-brand-400 bg-brand-500/10' : 'text-slate-300 hover:bg-slate-700'"
                      @click="selectLanguage(opt.value)"
                    >
                      <span class="font-mono">{{ opt.label }}</span>
                      <svg v-if="editLanguage === opt.value" class="w-3.5 h-3.5 text-brand-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
                    </button>
                    <div v-if="filteredLangOptions.length === 0" class="px-3 py-3 text-[11px] text-slate-500 text-center">无匹配语言</div>
                  </div>
                </div>
              </Teleport>
            </div>
            <div class="flex-1" />
            <button class="text-[10px] text-slate-400 hover:text-slate-200" @click="copyCode">复制</button>
          </div>
          <div class="relative" style="min-height: 3em">
            <!-- 底层：实时语法高亮渲染 -->
            <pre
              ref="codePreRef"
              class="p-4 pr-12 text-sm font-mono leading-relaxed whitespace-pre-wrap break-words m-0"
              aria-hidden="true"
            ><code class="hljs-code-block" v-html="highlightedEditCodeOrBlank" /></pre>
            <!-- 上层：透明文字的 textarea 用于输入 -->
            <textarea
              ref="inputRef"
              v-model="editText"
              class="absolute inset-0 w-full h-full resize-none bg-transparent text-transparent [-webkit-text-fill-color:transparent] caret-white p-4 pr-12 text-sm font-mono leading-relaxed outline-none overflow-auto selection:bg-brand-500/20 selection:text-transparent selection:[-webkit-text-fill-color:transparent]"
              spellcheck="false"
              placeholder="输入代码..."
              @keydown.escape="cancelEdit"
              @keydown="onEditKeydown"
              @paste="onPaste"
              @scroll="syncCodeScroll"
              @blur="saveCodeEdit"
            />
            <!-- 右上角复制按钮 -->
            <button
              v-if="editText"
              class="absolute top-2 right-2 w-7 h-7 flex items-center justify-center rounded-lg bg-slate-700/60 text-slate-400 hover:text-white hover:bg-slate-600 transition-all"
              title="复制代码"
              @click.stop="copyCode"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
            </button>
          </div>
        </div>
      </div>

      <!-- 引用 -->
      <blockquote
        v-else-if="block.type === 'quote'"
        class="border-l-4 border-brand-300 pl-4 py-1 text-slate-600 italic cursor-text"
        @click="startEdit"
      >
        <span v-if="!editing" :class="{ [placeholderClass]: !text }" v-html="formattedText || '引用内容'" />
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none text-slate-600 italic"
          @blur="saveEdit"
          @keydown.enter.exact="$event.preventDefault(); onEnterInEdit()"
          @keydown.escape="cancelEdit"
          @keydown="onEditKeydown"
          @input="autoResize"
          @paste="onPaste"
        />
      </blockquote>

      <!-- 列表 / 任务列表 -->
      <div v-else-if="block.type === 'list'" class="py-1">
        <!-- 任务列表 -->
        <div v-if="isTask && !editing" class="space-y-0.5">
          <div
            v-for="(item, i) in listItems"
            :key="i"
            class="flex items-start gap-2 py-0.5 group cursor-pointer"
            @click="toggleTaskItem(i)"
          >
            <span class="w-4 h-4 mt-0.5 rounded border-2 shrink-0 flex items-center justify-center transition-colors"
              :class="item.checked ? 'bg-brand-500 border-brand-500 text-white' : 'border-slate-300 hover:border-brand-400'"
            >
              <svg v-if="item.checked" class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>
            </span>
            <span class="text-slate-700 leading-relaxed" :class="{ 'line-through text-slate-400': item.checked }" v-html="renderInlineMarkdown(item.text) || '任务项'" />
          </div>
        </div>
        <!-- 普通列表显示 -->
        <div v-else-if="!editing" class="cursor-text" @click="startEdit">
          <p v-if="!listText" class="text-slate-400">{{ isOrdered ? '1. 列表项...' : '• 列表项...' }}</p>
          <p v-else class="text-slate-700 leading-relaxed">
            <span v-if="!isTask" class="text-slate-400 mr-1">{{ isOrdered ? '1. ' : '• ' }}</span>
            <span v-html="formattedListText" />
          </p>
        </div>
        <!-- 编辑模式 -->
        <div v-else class="flex items-start gap-1">
          <span v-if="isTask" class="w-4 h-4 mt-1.5 rounded border-2 border-slate-300 shrink-0" />
          <span v-else class="text-slate-400 pt-1.5">{{ isOrdered ? '1.' : '•' }}</span>
          <textarea
            ref="inputRef"
            v-model="editText"
            class="flex-1 resize-none bg-transparent border-none outline-none text-slate-700 leading-relaxed"
            @blur="saveListEdit"
            @keydown.enter.exact.prevent="onEnterInEditList"
            @keydown.escape="cancelEdit"
            @keydown="onEditKeydown"
            @input="autoResize"
            @paste="onPaste"
          />
        </div>
      </div>

      <!-- 分割线 -->
      <hr
        v-else-if="block.type === 'divider'"
        class="my-4 border-slate-300 cursor-pointer hover:border-brand-300 transition-colors"
        :class="dividerClass"
        @click="toggleDividerStyle"
        :title="'分割线 (' + (dividerStyleName) + ')，点击切换样式'"
      />

      <!-- 页面链接 -->
      <div
        v-else-if="block.type === 'page_link'"
        class="flex items-center gap-2 px-3 py-2 bg-brand-50 rounded-xl text-brand-700 cursor-pointer hover:bg-brand-100 transition-colors my-1"
        @click="navigateToPage"
      >
        <span>📎</span>
        <span class="font-medium">{{ linkTitle || '子页面' }}</span>
      </div>

      <!-- 图片 -->
      <div v-else-if="block.type === 'image'" class="my-2">
        <img v-if="imageUrl" :src="imageUrl" :alt="imageAlt" class="max-w-full rounded-xl cursor-pointer" @click="startEdit" />
        <div
          v-else-if="!editing"
          class="px-4 py-3 bg-slate-50 rounded-xl text-sm text-slate-400 text-center cursor-pointer hover:bg-slate-100"
          @click="startEdit"
        >🖼️ 点击添加图片URL</div>
        <div v-else class="flex gap-2">
          <input
            ref="inputRef"
            v-model="editText"
            class="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none focus:border-brand-400"
            placeholder="输入图片URL或粘贴图片..."
            @keydown.enter.prevent="onEnterInEdit"
            @keydown.escape="cancelEdit"
            @paste="onPaste"
            @blur="saveEdit"
          />
        </div>
      </div>

      <!-- 提示框 -->
      <div v-else-if="block.type === 'callout'" class="px-4 py-3 rounded-xl my-1" :class="calloutClass">
        <span v-if="!editing" class="cursor-text" :class="{ 'opacity-60': !text }" @click="startEdit" v-html="formattedText || '提示内容'" />
        <textarea
          v-else
          ref="inputRef"
          v-model="editText"
          class="w-full resize-none bg-transparent border-none outline-none"
          @blur="saveEdit"
          @keydown.escape="cancelEdit"
          @keydown="onEditKeydown"
          @input="autoResize"
          @paste="onPaste"
        />
      </div>

      <!-- 表格 -->
      <div v-else-if="block.type === 'table'" class="my-2">
        <!-- 非编辑模式：显示渲染后的表格 -->
        <div v-if="!editing" class="overflow-x-auto border border-slate-200 rounded-xl" @click="startEdit">
          <table v-if="tableData.headers.length" class="w-full border-collapse text-sm min-w-[400px]">
            <thead>
              <tr class="bg-slate-50">
                <th v-for="(h, hi) in tableData.headers" :key="hi" class="border border-slate-200 px-3 py-2 text-left font-semibold text-slate-600 whitespace-nowrap">
                  <span v-html="renderInlineMarkdown(h)" />
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in tableData.rows" :key="ri" class="hover:bg-slate-50/50">
                <td v-for="(cell, ci) in row" :key="ci" class="border border-slate-200 px-3 py-2 text-slate-700" v-html="renderInlineMarkdown(cell)" />
              </tr>
            </tbody>
          </table>
          <div v-if="!tableData.headers.length" class="px-4 py-3 text-sm text-slate-400 text-center cursor-pointer">
            📊 点击编辑表格（格式：| 列1 | 列2 |）
          </div>
        </div>
        <!-- 编辑模式：可编辑表格 -->
        <div v-else class="overflow-x-auto border-2 border-brand-300 rounded-xl">
          <div class="flex items-center gap-1 px-2 py-1.5 bg-brand-50 border-b border-brand-200">
            <span class="text-xs text-brand-600 font-semibold">📊 表格编辑</span>
            <div class="flex-1" />
            <button class="px-2 py-0.5 text-xs rounded hover:bg-brand-200 text-brand-700 transition-colors" title="添加行" @click.stop="addTableRow">+ 行</button>
            <button class="px-2 py-0.5 text-xs rounded hover:bg-brand-200 text-brand-700 transition-colors" title="添加列" @click.stop="addTableCol">+ 列</button>
            <button class="px-2 py-0.5 text-xs rounded hover:bg-red-100 text-red-600 transition-colors" title="删除行" @click.stop="deleteTableRow">- 行</button>
            <button class="px-2 py-0.5 text-xs rounded hover:bg-red-100 text-red-600 transition-colors" title="删除列" @click.stop="deleteTableCol">- 列</button>
            <div class="w-px h-4 bg-brand-200 mx-1" />
            <button class="px-2 py-0.5 text-xs rounded bg-brand-500 text-white hover:bg-brand-600 transition-colors" @click.stop="saveTableEdit">完成</button>
          </div>
          <table class="w-full border-collapse text-sm min-w-[400px]">
            <thead>
              <tr class="bg-slate-50/80">
                <th v-for="(h, hi) in editTableHeaders" :key="hi" class="border border-slate-200 px-2 py-1">
                  <input
                    v-model="editTableHeaders[hi]"
                    class="w-full bg-transparent border-none outline-none text-slate-700 font-semibold text-left py-1"
                    placeholder="表头..."
                    @keydown.enter.prevent="onTableEnter($event, 'header', hi)"
                    @keydown.escape="saveTableEdit"
                  />
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in editTableRows" :key="ri">
                <td v-for="(cell, ci) in row" :key="ci" class="border border-slate-200 px-2 py-1">
                  <input
                    v-model="editTableRows[ri][ci]"
                    class="w-full bg-transparent border-none outline-none text-slate-700 py-1"
                    :placeholder="'单元格...'"
                    @keydown.enter.prevent="onTableEnter($event, 'cell', ri, ci)"
                    @keydown.escape="saveTableEdit"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- 默认/未知 -->
      <div v-else class="text-sm text-slate-400 py-1">[{{ block.type }}]</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch, type Ref } from 'vue'
import type { Block, PageTreeNode, TableBlockContent } from '@/types'
import { filesApi } from '@/api/files'
import hljs from 'highlight.js'
import python from 'highlight.js/lib/languages/python'
import bash from 'highlight.js/lib/languages/bash'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import javascript from 'highlight.js/lib/languages/javascript'
import json from 'highlight.js/lib/languages/json'
import typescript from 'highlight.js/lib/languages/typescript'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import markdown from 'highlight.js/lib/languages/markdown'

hljs.registerLanguage('python', python)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('sh', bash)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('js', javascript)
hljs.registerLanguage('json', json)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('ts', typescript)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('md', markdown)

const props = defineProps<{
  block: Block
  allPages?: PageTreeNode[]
  settings?: {
    adaptiveWidth?: boolean
    smallFont?: boolean
    showToc?: boolean
    autoNumbering?: boolean
  }
  headingNumber?: string
  /** Custom placeholder text shown when the paragraph block is empty */
  contentPlaceholder?: string
}>()

const emit = defineEmits<{
  save: [content: Record<string, unknown>]
  changeType: [newType: string]
  navigate: [pageId: number]
  delete: []
  duplicate: []
  moveUp: []
  moveDown: []
  createBelow: []
  insertAbove: []
  insertBelow: []
  createImage: [url: string]
  moveTo: [sourceIndex: number, targetIndex: number, position: 'above' | 'below']
}>()

const showHandle = ref(false)
const editing = ref(false)
const editText = ref('')
const editLanguage = ref('')
const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)
const codePreRef = ref<HTMLElement | null>(null)

// ===== 表格编辑状态 =====
const editTableHeaders = ref<string[]>([])
const editTableRows = ref<string[][]>([])

// ===== 空 Block 双击 Backspace 删除 =====
const backspacePressedOnce = ref(false)

// 内容变化时重置 Backspace 标志位
watch(editText, () => {
  backspacePressedOnce.value = false
})

// ===== 拖拽排序状态 =====
const isDragging = ref(false)
const dragOverPosition = ref<'above' | 'below' | null>(null)
let dragSourceIndex = -1

function onDragStart(e: DragEvent) {
  if (!e.dataTransfer) return
  isDragging.value = true
  dragSourceIndex = getBlockIndex()
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(props.block.id))
}

function onDragEnd() {
  isDragging.value = false
  dragOverPosition.value = null
}

function onDragOver(e: DragEvent) {
  if (!e.dataTransfer || isDragging.value) return
  e.dataTransfer.dropEffect = 'move'
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  const midY = rect.top + rect.height / 2
  dragOverPosition.value = e.clientY < midY ? 'above' : 'below'
}

function onDragLeave() {
  dragOverPosition.value = null
}

function onDrop(e: DragEvent) {
  // ⚠️ 必须在清空 dragOverPosition 之前读取 position，否则总是 'below'
  const position = dragOverPosition.value || 'below'
  dragOverPosition.value = null
  const targetIndex = getBlockIndex()
  if (targetIndex < 0) return

  // 从 dataTransfer 中读取源 block ID（跨实例可靠传递）
  const sourceId = e.dataTransfer?.getData('text/plain')
  const sourceIndex = sourceId ? getBlockIndexById(sourceId) : dragSourceIndex

  if (sourceIndex >= 0 && targetIndex !== sourceIndex) {
    emit('moveTo', sourceIndex, targetIndex, position)
  }
}

/** 根据 block id 在 DOM 中查找索引 */
function getBlockIndexById(blockId: string): number {
  const el = document.querySelector(`[data-block-id="${blockId}"]`)
  if (!el) return -1
  const parent = el.parentElement
  if (!parent) return -1
  const items = parent.querySelectorAll('[data-block-id]')
  for (let i = 0; i < items.length; i++) {
    if (items[i].getAttribute('data-block-id') === blockId) return i
  }
  return -1
}

function getBlockIndex(): number {
  const el = document.querySelector(`[data-block-id="${props.block.id}"]`)
  if (!el) return -1
  const parent = el.parentElement
  if (!parent) return -1
  const items = parent.querySelectorAll('[data-block-id]')
  for (let i = 0; i < items.length; i++) {
    if (items[i].getAttribute('data-block-id') === String(props.block.id)) return i
  }
  return -1
}

function onMouseLeave() {
  showHandle.value = false
  dragOverPosition.value = null
}

// ===== 语言下拉选择器 =====
const showLangDropdown = ref(false)
const langSearchText = ref('')
const langSearchInput = ref<HTMLInputElement>()
const langDropdownPanel = ref<HTMLElement>()
const langDropdownStyle = ref<Record<string, string>>({ top: '0px', left: '0px' })

const languageOptions = [
  { label: 'Bash / Shell', value: 'bash' },
  { label: 'CSS', value: 'css' },
  { label: 'HTML / XML', value: 'html' },
  { label: 'JavaScript / JS', value: 'javascript' },
  { label: 'JSON', value: 'json' },
  { label: 'Markdown / MD', value: 'text' },
  { label: 'Python', value: 'python' },
  { label: 'SQL', value: 'sql' },
  { label: 'TypeScript / TS', value: 'typescript' },
  { label: 'YAML / YML', value: 'yaml' },
  { label: '纯文本', value: 'text' },
]

const filteredLangOptions = computed(() => {
  const q = langSearchText.value.toLowerCase().trim()
  if (!q) return languageOptions
  return languageOptions.filter(
    opt => opt.label.toLowerCase().includes(q) || opt.value.toLowerCase().includes(q)
  )
})

function selectLanguage(lang: string) {
  editLanguage.value = lang
  showLangDropdown.value = false
  langSearchText.value = ''
  // 选择完成后重新聚焦 textarea，保持编辑连贯性
  nextTick(() => inputRef.value?.focus())
}

/** Enter 键选择第一个过滤后的语言 */
function selectFirstFilteredLang() {
  const first = filteredLangOptions.value[0]
  if (first) selectLanguage(first.value)
}

// 语言下拉打开时：计算面板定位 & 自动聚焦搜索框
watch(showLangDropdown, (v) => {
  if (!v) return
  // 定位到触发按钮下方
  const btn = document.querySelector<HTMLElement>('[data-code-lang-btn]')
  if (btn) {
    const rect = btn.getBoundingClientRect()
    langDropdownStyle.value = { top: `${rect.bottom + 4}px`, left: `${Math.min(rect.left, window.innerWidth - 240)}px` }
  }
  langSearchText.value = ''
  nextTick(() => {
    langSearchInput.value?.focus()
    // 面板渲染后做视口微调
    if (langDropdownPanel.value) {
      const pr = langDropdownPanel.value.getBoundingClientRect()
      if (pr.bottom > window.innerHeight - 8) {
        langDropdownStyle.value.top = `${Math.max(4, btn?.getBoundingClientRect().top ?? pr.top - pr.height - 4)}px`
      }
    }
  })
})

// 新创建的空 block 自动进入编辑模式（有 contentPlaceholder 时跳过，以便显示占位提示）
onMounted(() => {
  if (props.contentPlaceholder) return
  const contentText = String(props.block.content.text || props.block.content.code || props.block.content.url || '')
  const hasTableHeaders = Array.isArray(props.block.content.headers) && (props.block.content.headers as unknown[]).length > 0
  if (!contentText && !hasTableHeaders && ['paragraph', 'heading', 'quote', 'callout', 'list', 'code', 'image', 'table'].includes(props.block.type)) {
    startEdit()
  }
})

const text = computed(() => String(props.block.content.text || ''))
const code = computed(() => String(props.block.content.code || ''))
const language = computed(() => String(props.block.content.language || 'text'))
const level = computed(() => Number(props.block.content.level || 2))
const isOrdered = computed(() => Boolean(props.block.content.ordered))
const listText = computed(() => {
  const items = props.block.content.items as string[] | undefined
  return items?.join(', ') || String(props.block.content.text || '')
})
const linkTitle = computed(() => String(props.block.content.title || ''))
const pageId = computed(() => Number(props.block.content.page_id || 0))
const isCentered = computed(() => Boolean(props.block.content.centered))
const bgColor = computed(() => String(props.block.content.bg_color || ''))
const textColor = computed(() => String(props.block.content.text_color || ''))
const dividerStyle = computed(() => String(props.block.content.divider_style || 'solid'))
const dividerClass = computed(() => {
  const s = dividerStyle.value
  if (s === 'dashed') return 'border-dashed'
  if (s === 'dotted') return 'border-dotted'
  return 'border-solid'
})
const dividerStyleName = computed(() => {
  const s = dividerStyle.value
  if (s === 'dashed') return '虚线'
  if (s === 'dotted') return '点线'
  return '实线'
})
const imageUrl = computed(() => String(props.block.content.url || ''))
const imageAlt = computed(() => String(props.block.content.alt || ''))
const isTask = computed(() => Boolean(props.block.content.task))
const listItems = computed(() => {
  const raw = props.block.content.items
  if (Array.isArray(raw)) {
    return raw.map((item: unknown) => {
      if (typeof item === 'object' && item !== null) return item as { text: string; checked?: boolean }
      return { text: String(item), checked: false }
    })
  }
  return []
})
const tableData = computed(() => ({
  headers: (props.block.content.headers as string[]) || [],
  rows: (props.block.content.rows as string[][]) || [],
}))

const blockStyle = computed(() => {
  const style: Record<string, string> = {}
  if (isCentered.value) style.textAlign = 'center'
  if (bgColor.value) style.background = bgColor.value
  if (textColor.value) style.color = textColor.value
  return style
})

const headingClass = computed(() => ({
  1: 'text-3xl',
  2: 'text-2xl',
  3: 'text-xl',
  4: 'text-lg',
  5: 'text-base',
  6: 'text-sm',
}[level.value] || 'text-2xl'))

const calloutClass = computed(() => {
  const t = String(props.block.content.type || 'info')
  const map: Record<string, string> = {
    info: 'bg-blue-50 text-blue-800',
    warning: 'bg-amber-50 text-amber-800',
    success: 'bg-green-50 text-green-800',
    error: 'bg-red-50 text-red-800',
  }
  return map[t] || map.info
})

// ===== Block 操作菜单 =====
const blockMenuOpen = ref(false)
const blockMenuStyle = ref<Record<string, string>>({})
const blockMenuPopup = ref<HTMLElement>()
const showColorPicker = ref(false)

// 插入按钮单向显示
const showTopInsert = ref(false)
const showBottomInsert = ref(false)
const showHeadingSubMenu = ref(false)
const showListSubMenu = ref(false)
const headingSubTrigger = ref<HTMLElement>()
const listSubTrigger = ref<HTMLElement>()
const headingSubStyle = ref<Record<string, string>>({})
const listSubStyle = ref<Record<string, string>>({})
let headingSubTimer: ReturnType<typeof setTimeout> | null = null
let listSubTimer: ReturnType<typeof setTimeout> | null = null

/** 关闭所有子菜单（用于菜单关闭时清理） */
function closeAllSubMenus() {
  if (headingSubTimer) { clearTimeout(headingSubTimer); headingSubTimer = null }
  if (listSubTimer) { clearTimeout(listSubTimer); listSubTimer = null }
  showHeadingSubMenu.value = false
  showListSubMenu.value = false
}

function openHeadingSubMenu() {
  // 关闭另一个子菜单
  if (listSubTimer) { clearTimeout(listSubTimer); listSubTimer = null }
  showListSubMenu.value = false
  // 打开当前
  if (headingSubTimer) clearTimeout(headingSubTimer)
  const el = headingSubTrigger.value
  if (el) {
    const rect = el.getBoundingClientRect()
    headingSubStyle.value = { top: `${rect.top}px`, left: `${rect.right}px` }
  }
  showHeadingSubMenu.value = true
}

function scheduleHideHeadingSub() {
  if (headingSubTimer) clearTimeout(headingSubTimer)
  headingSubTimer = setTimeout(() => { showHeadingSubMenu.value = false }, 100)
}

/** 从子菜单进入时立即清除延迟 */
function enterHeadingSubMenu() {
  if (headingSubTimer) { clearTimeout(headingSubTimer); headingSubTimer = null }
  showHeadingSubMenu.value = true
}

function openListSubMenu() {
  // 关闭另一个子菜单
  if (headingSubTimer) { clearTimeout(headingSubTimer); headingSubTimer = null }
  showHeadingSubMenu.value = false
  // 打开当前
  if (listSubTimer) clearTimeout(listSubTimer)
  const el = listSubTrigger.value
  if (el) {
    const rect = el.getBoundingClientRect()
    listSubStyle.value = { top: `${rect.top}px`, left: `${rect.right}px` }
  }
  showListSubMenu.value = true
}

function scheduleHideListSub() {
  if (listSubTimer) clearTimeout(listSubTimer)
  listSubTimer = setTimeout(() => { showListSubMenu.value = false }, 100)
}

function enterListSubMenu() {
  if (listSubTimer) { clearTimeout(listSubTimer); listSubTimer = null }
  showListSubMenu.value = true
}

function onHandleMouseMove(e: MouseEvent) {
  const el = e.currentTarget as HTMLElement
  const rect = el.getBoundingClientRect()
  const midY = rect.top + rect.height / 2
  showTopInsert.value = e.clientY < midY
  showBottomInsert.value = e.clientY >= midY
}

function onHandleMouseLeave() {
  showTopInsert.value = false
  showBottomInsert.value = false
}

const typeOptions = [
  { type: 'paragraph', label: '段落 ¶', icon: '¶' },
  { type: 'heading', label: '标题 H', icon: 'H' },
  { type: 'list', label: '列表 •', icon: '•' },
  { type: 'quote', label: '引用 ❝', icon: '❝' },
  { type: 'code', label: '代码 </>', icon: '</>' },
  { type: 'divider', label: '分割线 —', icon: '—' },
  { type: 'table', label: '表格 ▦', icon: '▦' },
  { type: 'callout', label: '提示框 💡', icon: '💡' },
  { type: 'image', label: '图片 🖼️', icon: '🖼️' },
  { type: 'page_link', label: '页面链接 🔗', icon: '🔗' },
]

const colors = [
  '#ef4444', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899',
  '#fef3c7', '#fde68a', '#dbeafe', '#bfdbfe', '#dcfce7', '#bbf7d0', '#fce7f3', '#fbcfe8',
  '#f3e8ff', '#ddd6fe', '#e0f2fe', '#bae6fd', '#fff7ed', '#fed7aa', '#f1f5f9', '#e2e8f0',
]

// 常用文字颜色
const textColors = [
  { name: '红色', color: '#dc2626' },
  { name: '橙色', color: '#ea580c' },
  { name: '黄色', color: '#ca8a04' },
  { name: '绿色', color: '#16a34a' },
  { name: '青色', color: '#0891b2' },
  { name: '蓝色', color: '#2563eb' },
  { name: '紫色', color: '#7c3aed' },
  { name: '粉色', color: '#db2777' },
  { name: '墨绿', color: '#0d9488' },
  { name: '默认', color: 'transparent' },
]

function toggleBlockMenu(e: MouseEvent) {
  if (blockMenuOpen.value) {
    closeAllSubMenus()
  }
  blockMenuOpen.value = !blockMenuOpen.value
  if (!blockMenuOpen.value) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  blockMenuStyle.value = { top: `${rect.bottom + 4}px`, left: `${rect.left}px` }
  showColorPicker.value = false
  nextTick(() => adjustPopupToViewport(blockMenuStyle, rect, blockMenuPopup))
}

function changeType(newType: string) {
  blockMenuOpen.value = false
  if (newType !== props.block.type) {
    emit('changeType', newType)
  }
}

function setColor(color: string) {
  showColorPicker.value = false
  blockMenuOpen.value = false
  emit('save', { ...props.block.content, bg_color: color === 'transparent' ? '' : color })
}

/** 设置文字颜色 */
function setTextColor(color: string) {
  blockMenuOpen.value = false
  emit('save', { ...props.block.content, text_color: color === 'transparent' ? '' : color })
}

function toggleCenter() {
  blockMenuOpen.value = false
  emit('save', { ...props.block.content, centered: !isCentered.value })
}

/** 切换分割线样式：实线→虚线→点线→实线 */
function toggleDividerStyle() {
  const styles = ['solid', 'dashed', 'dotted']
  const cur = dividerStyle.value
  const nextIdx = (styles.indexOf(cur) + 1) % styles.length
  emit('save', { ...props.block.content, divider_style: styles[nextIdx] })
}

// ===== 右键菜单 =====
const ctxMenuOpen = ref(false)
const ctxMenuStyle = ref<Record<string, string>>({})
const ctxMenuPopup = ref<HTMLElement>()
function onContextMenu(e: MouseEvent) {
  ctxMenuOpen.value = true
  ctxMenuStyle.value = { top: `${e.clientY}px`, left: `${e.clientX}px` }
  const triggerRect = { top: e.clientY, bottom: e.clientY, left: e.clientX, right: e.clientX } as DOMRect
  nextTick(() => adjustPopupToViewport(ctxMenuStyle, triggerRect, ctxMenuPopup))
}
function quickConvert(type: string, extra?: number | boolean) {
  ctxMenuOpen.value = false
  const content: Record<string, unknown> = { ...props.block.content }
  if (type === 'heading') content.level = extra ?? 2
  else if (type === 'list') {
    content.ordered = extra ?? false
    content.items = text.value ? [text.value] : []
    delete content.text
  }
  emit('save', content)
  if (type !== props.block.type) {
    emit('changeType', type)
  }
}

/** 从 Block 菜单中快速转换（标题级别、列表类型等） */
function quickConvertFromMenu(type: string, extra?: number | boolean, task?: boolean) {
  blockMenuOpen.value = false
  const content: Record<string, unknown> = { ...props.block.content }
  if (type === 'heading') {
    content.level = extra ?? 2
  } else if (type === 'list') {
    content.ordered = extra ?? false
    if (task) {
      content.task = true
      content.items = text.value ? [{ text: text.value, checked: false }] : []
    } else {
      delete content.task
      content.items = text.value ? [text.value] : []
    }
    delete content.text
  }
  emit('save', content)
  if (type !== props.block.type) {
    emit('changeType', type)
  }
}

// ===== 编辑逻辑 =====
async function startEdit(e?: MouseEvent) {
  if (['paragraph', 'heading', 'quote', 'callout', 'list', 'code', 'image', 'table'].includes(props.block.type)) {
    editing.value = true
    if (props.block.type === 'code') {
      editText.value = code.value
      editLanguage.value = language.value
    } else if (props.block.type === 'image') {
      editText.value = String(props.block.content.url || '')
    } else if (props.block.type === 'table') {
      editTableHeaders.value = [...tableData.value.headers]
      editTableRows.value = tableData.value.rows.map(row => [...row])
      // 至少保证有一列一行
      if (editTableHeaders.value.length === 0) {
        editTableHeaders.value = ['列1', '列2']
      }
      if (editTableRows.value.length === 0) {
        editTableRows.value = [editTableHeaders.value.map(() => '')]
      } else {
        // 每行的列数补齐到与表头一致
        for (let ri = 0; ri < editTableRows.value.length; ri++) {
          while (editTableRows.value[ri].length < editTableHeaders.value.length) {
            editTableRows.value[ri].push('')
          }
        }
      }
      await nextTick()
      // 聚焦第一个表头输入框
      const firstInput = (inputRef.value as HTMLElement)?.closest('.overflow-x-auto')?.querySelector('input')
      if (firstInput instanceof HTMLInputElement) firstInput.focus()
    } else {
      editText.value = text.value
    }
    await nextTick()
    inputRef.value?.focus()
    // 确保 textarea 高度与已有内容一致，避免编辑框变小
    nextTick(() => autoResize())
  }
}

function autoResize() {
  // 代码块使用 pre+textarea 叠加层方案，容器高度由 pre 驱动，不需要手动 resize
  if (props.block.type === 'code') return
  const el = inputRef.value
  if (el instanceof HTMLTextAreaElement) {
    // 移除 rows 属性约束，让 scrollHeight 生效
    el.removeAttribute('rows')
    el.style.height = 'auto'
    el.style.height = el.scrollHeight + 'px'
  }
}

/** 代码块编辑时同步 textarea 滚动位置到 pre 元素 */
function syncCodeScroll() {
  const pre = codePreRef.value
  const ta = inputRef.value
  if (pre && ta) {
    pre.scrollTop = ta.scrollTop
    pre.scrollLeft = ta.scrollLeft
  }
}

/** 粘贴后触发 autoResize，并处理剪贴板图片粘贴 */
function onPaste(e: ClipboardEvent) {
  // 检查剪贴板中是否有图片
  const items = e.clipboardData?.items
  if (items) {
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const blob = item.getAsFile()
        if (blob) {
          handleImagePaste(blob)
          return
        }
      }
    }
  }
  nextTick(() => autoResize())
}

/** 处理剪贴板图片粘贴：上传并创建图片 Block */
async function handleImagePaste(blob: Blob) {
  try {
    const file = new File([blob], `paste-${Date.now()}.png`, { type: blob.type || 'image/png' })
    const { data } = await filesApi.upload(file)
    if (data.url) {
      // 如果当前 Block 是空段落，转换为图片 Block
      const isEmpty = !text.value && ['paragraph', 'heading'].includes(props.block.type)
      if (isEmpty) {
        editing.value = false
        emit('save', { ...props.block.content, url: data.url, alt: '' })
        emit('changeType', 'image')
      } else {
        // 保存当前内容，并在下方创建新的图片 Block
        editing.value = false
        emit('save', { ...props.block.content, text: editText.value })
        emit('createImage', data.url)
      }
    }
  } catch {
    // 上传失败，静默忽略
  }
}

function saveEdit() {
  if (!editing.value) return
  const newText = editText.value.trim()
  editing.value = false

  if (props.block.type === 'image') {
    if (newText !== String(props.block.content.url || '')) {
      emit('save', { ...props.block.content, url: newText, alt: '' })
    }
    return
  }

  if (props.block.type === 'table') {
    saveTableEdit()
    return
  }

  // Markdown 快捷转换
  const md = checkMarkdownShortcut(newText)
  if (md) {
    emit('save', { ...props.block.content, ...md.content })
    if (md.type && md.type !== props.block.type) {
      emit('changeType', md.type)
    }
    return
  }

  if (newText !== text.value) {
    emit('save', { ...props.block.content, text: newText })
  }
}

function saveCodeEdit() {
  if (!editing.value) return
  // 语言下拉打开中：下拉面板已通过 Teleport+mousedown.prevent 隔离交互，
  // 此处 blur 可能由面板内部搜索框焦点引起，直接跳过保存
  if (showLangDropdown.value) return
  editing.value = false
  const newCode = editText.value
  const newLang = editLanguage.value.trim() || 'text'
  if (newCode !== code.value || newLang !== language.value) {
    emit('save', { ...props.block.content, code: newCode, language: newLang })
  }
}

/** Enter 键：保存当前 Block 并创建新 Block */
function onEnterInEdit() {
  if (!editing.value) return
  saveEdit()
  nextTick(() => emit('createBelow'))
}

function onEnterInEditList() {
  if (!editing.value) return
  saveListEdit()
  nextTick(() => emit('createBelow'))
}

function saveListEdit() {
  if (!editing.value) return
  const newText = editText.value.trim()
  editing.value = false
  if (newText !== text.value) {
    emit('save', { ...props.block.content, items: [newText], text: newText })
  }
}

/** 将弹出面板调整到视口内：如果下方放不下则翻转到触发元素上方，右边界溢出则向左偏移 */
function adjustPopupToViewport(
  styleRef: Ref<Record<string, string>>,
  triggerRect: DOMRect,
  popupRef?: Ref<HTMLElement | undefined>,
  gap = 4,
) {
  const popup = popupRef?.value
  if (!popup) return
  const popupRect = popup.getBoundingClientRect()
  const vh = window.innerHeight
  const vw = window.innerWidth
  let newTop: string | undefined
  let newLeft: string | undefined

  // 底部溢出 → 翻转到上方
  if (popupRect.bottom > vh - 8) {
    newTop = `${Math.max(4, triggerRect.top - popupRect.height - gap)}px`
  }
  // 右边界溢出 → 向左偏移
  if (popupRect.right > vw - 8) {
    newLeft = `${Math.max(4, vw - popupRect.width - 8)}px`
  }

  if (newTop || newLeft) {
    styleRef.value = {
      ...styleRef.value,
      ...(newTop ? { top: newTop } : {}),
      ...(newLeft ? { left: newLeft } : {}),
    }
  }
}

// ===== 表格编辑函数 =====
function saveTableEdit() {
  if (!editing.value) return
  editing.value = false
  // 过滤掉完全空的列
  const headers = editTableHeaders.value.map(h => h.trim())
  // 保留至少两列
  const cleanHeaders = headers.length >= 2 ? headers : ['列1', '列2']
  const cleanRows = editTableRows.value.map(row =>
    row.map(cell => cell.trim())
  )
  emit('save', {
    ...props.block.content,
    headers: cleanHeaders,
    rows: cleanRows.length > 0 ? cleanRows : [cleanHeaders.map(() => '')],
  })
}

function addTableRow() {
  const cols = editTableHeaders.value.length || 2
  const newRow = Array(cols).fill('')
  editTableRows.value.push(newRow)
}

function addTableCol() {
  editTableHeaders.value.push('新列')
  for (const row of editTableRows.value) {
    row.push('')
  }
}

function deleteTableRow() {
  if (editTableRows.value.length > 1) {
    editTableRows.value.pop()
  }
}

function deleteTableCol() {
  if (editTableHeaders.value.length > 1) {
    editTableHeaders.value.pop()
    for (const row of editTableRows.value) {
      row.pop()
    }
  }
}

/** 表格内 Enter 键：保存并创建下方 Block */
function onTableEnter(e: KeyboardEvent, _source: string, _ri?: number, _ci?: number) {
  // Shift+Enter 不处理，允许换行（由浏览器默认行为）
  if (e.shiftKey) return
  saveTableEdit()
  nextTick(() => emit('createBelow'))
}

function cancelEdit() {
  editing.value = false
  editText.value = text.value
}

// ===== 行内 Markdown → HTML 渲染 =====
function renderInlineMarkdown(text: string): string {
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  // 图片 ![...](...)
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="inline max-w-full rounded" loading="lazy" />')
  // 链接 [...](...)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-brand-600 underline decoration-brand-300 hover:decoration-brand-600" target="_blank" rel="noopener">$1</a>')
  // 粗体 **...** 或 __...__
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong class="font-semibold">$1</strong>')
  html = html.replace(/__([^_]+)__/g, '<strong class="font-semibold">$1</strong>')
  // 斜体 *...*
  html = html.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
  // 删除线 ~~...~~
  html = html.replace(/~~([^~]+)~~/g, '<del class="line-through text-slate-400">$1</del>')
  // 高亮 ==...==
  html = html.replace(/==([^=]+)==/g, '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>')
  // 行内代码 `...`
  html = html.replace(/`([^`]+)`/g, '<code class="bg-slate-100 text-pink-600 px-1 py-0.5 rounded text-[0.9em] font-mono">$1</code>')
  // 软换行 \n → <br>
  html = html.replace(/\n/g, '<br />')
  return html
}

const formattedText = computed(() => renderInlineMarkdown(text.value))
const formattedListText = computed(() => renderInlineMarkdown(listText.value))
const placeholderClass = 'text-slate-400 select-none'

// ===== 代码语法高亮 =====
const highlightedCode = computed(() => {
  const rawCode = code.value
  if (!rawCode) return ''
  const lang = language.value.toLowerCase()
  if (lang && hljs.getLanguage(lang)) {
    try {
      return hljs.highlight(rawCode, { language: lang }).value
    } catch {
      // 高亮失败时回退为纯文本
    }
  }
  return hljs.highlightAuto(rawCode).value
})

/** 编辑模式下实时语法高亮（底层 pre 渲染用），返回 HTML 字符串；空时返回换行占位防止 pre 塌陷 */
const highlightedEditCodeOrBlank = computed(() => {
  const rawCode = editText.value
  if (!rawCode) return '&#10;'
  const lang = editLanguage.value.toLowerCase()
  if (lang && hljs.getLanguage(lang)) {
    try {
      return hljs.highlight(rawCode, { language: lang }).value
    } catch {
      // 高亮失败时回退
    }
  }
  return hljs.highlightAuto(rawCode).value
})

/** 编辑模式下实时语法高亮的原始版（保留用于其他地方？已合并到上方） */

// ===== 编辑模式键盘快捷键 =====
function onEditKeydown(e: KeyboardEvent) {
  // 空 Block 双击 Backspace 删除
  if (e.key === 'Backspace') {
    const el = inputRef.value
    const isEmpty = !editText.value
    const atStart = el ? (el.selectionStart ?? 0) === 0 && (el.selectionEnd ?? 0) === 0 : true
    if (isEmpty && atStart) {
      if (backspacePressedOnce.value) {
        e.preventDefault()
        backspacePressedOnce.value = false
        editing.value = false
        emit('delete')
      } else {
        e.preventDefault()
        backspacePressedOnce.value = true
      }
      return
    }
    backspacePressedOnce.value = false
  } else {
    backspacePressedOnce.value = false
  }

  const ctrl = e.ctrlKey || e.metaKey
  if (ctrl && e.key === 'b') {
    e.preventDefault(); wrapSelection('**')
  } else if (ctrl && e.key === 'i') {
    e.preventDefault(); wrapSelection('*')
  } else if (ctrl && e.key === 'u') {
    e.preventDefault(); wrapSelection('<u>', '</u>')
  } else if (ctrl && e.key === 'k') {
    e.preventDefault(); insertLink()
  } else if (ctrl && e.shiftKey && e.key === 'K') {
    e.preventDefault(); emit('changeType', 'code')
  } else if (ctrl && e.key >= '1' && e.key <= '6') {
    e.preventDefault()
    const lv = parseInt(e.key)
    if (props.block.type !== 'heading' || level.value !== lv) {
      emit('save', { ...props.block.content, text: editText.value, level: lv })
      emit('changeType', 'heading')
    }
  }
}

function wrapSelection(wrapper: string, endWrapper?: string) {
  const el = inputRef.value
  if (!el) return
  const start = el.selectionStart ?? 0
  const end = el.selectionEnd ?? 0
  const before = editText.value.slice(0, start)
  const selected = editText.value.slice(start, end)
  const after = editText.value.slice(end)
  editText.value = before + wrapper + selected + (endWrapper || wrapper) + after
  nextTick(() => {
    el.focus()
    el.setSelectionRange(start + wrapper.length, start + wrapper.length + selected.length)
  })
}

function insertLink() {
  const el = inputRef.value
  if (!el) return
  const start = el.selectionStart ?? 0
  const end = el.selectionEnd ?? 0
  const selected = editText.value.slice(start, end) || '链接文字'
  const url = prompt('输入链接URL:', 'https://')
  if (url) {
    const before = editText.value.slice(0, start)
    const after = editText.value.slice(end)
    editText.value = before + `[${selected}](${url})` + after
    nextTick(() => el.focus())
  }
}

function insertAtCursor(text: string) {
  const el = inputRef.value
  if (!el) return
  const start = el.selectionStart ?? 0
  const before = editText.value.slice(0, start)
  const after = editText.value.slice(start)
  editText.value = before + text + after
  nextTick(() => {
    el.focus()
    const pos = start + text.length
    el.setSelectionRange(pos, pos)
  })
}

function checkMarkdownShortcut(input: string): { type?: string; content: Record<string, unknown> } | null {
  // # 标题
  const hMatch = input.match(/^(#{1,6})\s+(.+)/)
  if (hMatch) {
    return { type: 'heading', content: { level: hMatch[1].length, text: hMatch[2] } }
  }
  // --- / *** / ___ 分割线
  if (/^[-*_]{3,}$/.test(input)) {
    return { type: 'divider', content: {} }
  }
  // - [ ] / - [x] 任务列表
  const taskMatch = input.match(/^[-*+]\s+\[([ xX])\]\s+(.+)/)
  if (taskMatch) {
    return { type: 'list', content: { ordered: false, task: true, items: [{ text: taskMatch[2], checked: taskMatch[1].toLowerCase() === 'x' }] } }
  }
  // - 无序列表
  if (/^[-*+]\s/.test(input)) {
    return { type: 'list', content: { ordered: false, items: [{ text: input.replace(/^[-*+]\s/, '') }] } }
  }
  // 1. 有序列表
  if (/^\d+\.\s/.test(input)) {
    return { type: 'list', content: { ordered: true, items: [{ text: input.replace(/^\d+\.\s/, '') }] } }
  }
  // > 引用
  if (input.startsWith('> ')) {
    return { type: 'quote', content: { text: input.slice(2) } }
  }
  // ``` 代码
  if (input.startsWith('```')) {
    return { type: 'code', content: { language: input.slice(3).trim() || 'text', code: '' } }
  }
  // $$ 数学公式块
  if (input.startsWith('$$')) {
    return { type: 'code', content: { language: 'math', code: '' } }
  }
  // | ... | ... | 表格（支持多行粘贴）
  const lines = input.split('\n')
  if (lines.length >= 2) {
    // 检测多行 Markdown 表格：表头行 + 分隔行 + 可选数据行
    const headerLine = lines[0].trim()
    const sepLine = (lines[1] || '').trim()
    const headerMatch = headerLine.match(/^\|(.+)\|$/)
    const sepMatch = sepLine.match(/^\|[\s:-]+\|[\s|:-]+$/)
    if (headerMatch && sepMatch) {
      const headers = headerMatch[1].split('|').map(h => h.trim()).filter(Boolean)
      if (headers.length >= 2) {
        const rows: string[][] = []
        for (let li = 2; li < lines.length; li++) {
          const rowLine = lines[li].trim()
          const rowMatch = rowLine.match(/^\|(.+)\|$/)
          if (rowMatch) {
            const cells = rowMatch[1].split('|').map(c => c.trim())
            while (cells.length < headers.length) cells.push('')
            rows.push(cells)
          }
        }
        return { type: 'table', content: { headers, rows } }
      }
    }
  }
  // 单行表格：| col1 | col2 |
  const tableMatch = input.match(/^\|(.+)\|$/)
  if (tableMatch) {
    const headers = tableMatch[1].split('|').map(h => h.trim()).filter(Boolean)
    if (headers.length >= 2) {
      return { type: 'table', content: { headers, rows: [] } }
    }
  }
  return null
}

function navigateToPage() {
  if (pageId.value) emit('navigate', pageId.value)
}

async function copyCode() {
  // 编辑模式下复制正在编辑的代码，查看模式下复制已保存的代码
  const codeToCopy = editing.value && props.block.type === 'code' ? editText.value : code.value
  await navigator.clipboard.writeText(codeToCopy)
}

async function toggleTaskItem(index: number) {
  const items = [...listItems.value]
  if (items[index]) {
    items[index] = { ...items[index], checked: !items[index].checked }
    emit('save', { ...props.block.content, items })
  }
}
</script>

<style scoped>
.block-menu-item {
  @apply w-full flex items-center gap-2 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors text-left;
}

/* 插入按钮 */
.block-insert-btn {
  @apply absolute left-1/2 -translate-x-1/2 w-5 h-5 flex items-center justify-center rounded-full bg-white border border-transparent text-slate-400 hover:text-brand-500 hover:border-brand-300 hover:bg-brand-50 transition-all shadow-sm z-10;
}

/* 右侧展开子菜单 */
.sub-menu-right {
  @apply absolute left-full top-0 w-40 bg-white rounded-xl shadow-lg border border-slate-200 py-1 ml-1 max-h-48 overflow-y-auto;
}

/* 拖拽时保持操作区可见 */
.block-item [draggable="true"] {
  touch-action: none;
}
</style>

<!-- highlight.js 暗色主题（与 bg-slate-900 背景协调） -->
<style>
/* 代码高亮容器 - 重置为 highlight.js 控制颜色 */
.hljs-code-block {
  background: transparent !important;
  padding: 0 !important;
  color: #e2e8f0;
}

/* highlight.js 暗色主题 */
.hljs-code-block .hljs-keyword,
.hljs-code-block .hljs-selector-tag,
.hljs-code-block .hljs-literal,
.hljs-code-block .hljs-section,
.hljs-code-block .hljs-link {
  color: #c084fc;
}

.hljs-code-block .hljs-string,
.hljs-code-block .hljs-title.class_,
.hljs-code-block .hljs-title.class_ .hljs-title {
  color: #86efac;
}

.hljs-code-block .hljs-number,
.hljs-code-block .hljs-meta .hljs-string,
.hljs-code-block .hljs-built_in {
  color: #fde68a;
}

.hljs-code-block .hljs-title.function_ {
  color: #93c5fd;
}

.hljs-code-block .hljs-comment,
.hljs-code-block .hljs-quote {
  color: #64748b;
  font-style: italic;
}

.hljs-code-block .hljs-attr,
.hljs-code-block .hljs-attribute,
.hljs-code-block .hljs-variable,
.hljs-code-block .hljs-template-variable,
.hljs-code-block .hljs-type {
  color: #f9a8d4;
}

.hljs-code-block .hljs-meta,
.hljs-code-block .hljs-selector-attr,
.hljs-code-block .hljs-selector-pseudo {
  color: #c084fc;
}

.hljs-code-block .hljs-tag {
  color: #f472b6;
}

.hljs-code-block .hljs-name {
  color: #f472b6;
}

.hljs-code-block .hljs-regexp,
.hljs-code-block .hljs-symbol,
.hljs-code-block .hljs-template-tag,
.hljs-code-block .hljs-bullet,
.hljs-code-block .hljs-code {
  color: #fb923c;
}

.hljs-code-block .hljs-subst {
  color: #e2e8f0;
}

.hljs-code-block .hljs-formula {
  color: #67e8f9;
}

.hljs-code-block .hljs-selector-class {
  color: #86efac;
}

.hljs-code-block .hljs-params {
  color: #e2e8f0;
}
</style>
