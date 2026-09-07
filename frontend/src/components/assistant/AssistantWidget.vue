<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { assistantApi, type ChatMsg } from '@/api/assistant'
import { ragApi } from '@/api/files'
import { useAssistantStore } from '@/stores/assistant'
import { useOrgStore } from '@/stores/org'
import type { RagSource } from '@/types'

const { settings, applyCustomCss, runCustomJs } = useAssistantStore()
const orgStore = useOrgStore()
const router = useRouter()

const open = ref(false)
const tab = ref<'chat' | 'settings'>('chat')
const busy = ref(false)
const error = ref('')
const messages = ref<ChatMsg[]>([
  { role: 'assistant', content: settings.greeting },
])
const input = ref('')
const ragSources = ref<RagSource[]>([])
const listRef = ref<HTMLDivElement>()

const ballStyle = computed(() => ({
  width: `${settings.size}px`,
  height: `${settings.size}px`,
  background: settings.ballBg || 'linear-gradient(135deg,#6366f1,#a855f7)',
  fontSize: `${Math.max(16, settings.size * 0.52)}px`,
}))
const panelStyle = computed(() =>
  settings.panelBg ? { background: settings.panelBg } : {},
)

watch(open, async (v) => {
  if (v) {
    applyCustomCss(settings.customCss)
    await nextTick()
    runCustomJs(settings.customJs)
  }
})
watch(() => settings.customCss, (v) => { if (open.value) applyCustomCss(v) })

function hideBall() {
  settings.visible = false
  open.value = false
}

function reveal() {
  settings.visible = true
  open.value = true
  tab.value = 'settings'
}

function applyDiy() {
  applyCustomCss(settings.customCss)
  runCustomJs(settings.customJs)
  alert('已应用自定义 CSS/JS 与外观配置')
}

function resetDiy() {
  const { visible, size, ballBg, ballIcon, ballIconUrl, greeting, panelBg, mode, llm } = settings
  const defaultStore = {
    visible, size: 54, ballBg: 'linear-gradient(135deg,#6366f1,#a855f7)',
    ballIcon: '🤖', ballIconUrl: '', greeting: '你好呀 👋 我是你的 AI 助手，想问点什么？',
    panelBg: '', mode,
    llm: { ...llm, base_url: '', api_key: '', model: '', temperature: 0.7,
           system: '你是一位乐于助人的 AI 助手。回答请简洁、准确。' },
    customCss: '', customJs: '',
  } as typeof settings
  Object.assign(settings, defaultStore)
  applyCustomCss('')
}

function scrollBottom() {
  nextTick(() => {
    if (listRef.value) listRef.value.scrollTop = listRef.value.scrollHeight
  })
}

async function send() {
  const text = input.value.trim()
  if (!text || busy.value) return
  input.value = ''
  error.value = ''
  messages.value.push({ role: 'user', content: text })
  busy.value = true
  ragSources.value = []
  try {
    if (settings.mode === 'rag') {
      const pid = orgStore.activeProject?.id ?? null
      const { data } = await ragApi.ask(text, pid, 6)
      messages.value.push({ role: 'assistant', content: data.answer || '（无回答）' })
      ragSources.value = data.sources || []
    } else {
      const history = messages.value.slice(0, -1)
      const { data } = await assistantApi.chat([...history, { role: 'user', content: text }], {
        base_url: settings.llm.base_url,
        api_key: settings.llm.api_key,
        model: settings.llm.model,
        temperature: settings.llm.temperature,
        system: settings.llm.system,
      })
      messages.value.push({ role: 'assistant', content: data.reply || '（空回复）' })
    }
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail || '请求失败：请检查 LLM 配置或后端服务'
  } finally {
    busy.value = false
    scrollBottom()
  }
}

function openSource(src: RagSource) {
  open.value = false
  router.push({ path: `/notes/${src.slug}`, query: { project: src.project_id, anchor: src.heading_path || '' } })
}

onMounted(() => { if (settings.visible) applyCustomCss(settings.customCss) })
</script>

<template>
  <div>
    <!-- 迷你条：球被隐藏时的重显入口 -->
    <div
      v-if="!settings.visible"
      class="taot-assistant-mini fixed bottom-5 right-4 z-[9990] px-2 py-1 rounded-full bg-slate-800/80 text-white text-[11px] cursor-pointer select-none"
      title="显示 AI 助手"
      @click="reveal"
    >
      {{ settings.ballIcon || '🤖' }} AI 助手已隐藏 · 点击设置
    </div>

    <!-- 悬浮球 -->
    <button
      v-else
      class="taot-assistant-ball fixed right-4 bottom-5 z-[9990] rounded-full flex items-center justify-center text-white shadow-xl transition-transform hover:scale-110 cursor-pointer"
      :style="ballStyle"
      title="AI 助手"
      @click="open = !open"
    >
      <img v-if="settings.ballIconUrl" :src="settings.ballIconUrl" class="w-3/5 h-3/5 object-contain" alt="assistant" />
      <span v-else>{{ settings.ballIcon }}</span>
    </button>

    <!-- 助手面板 -->
    <div
      v-if="open"
      class="taot-assistant-panel fixed right-4 bottom-[calc(5rem)] z-[9995] w-[380px] max-w-[calc(100vw-2rem)] h-[560px] max-h-[calc(100vh-7rem)] rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden"
      :style="panelStyle"
    >
      <div class="taot-assistant-head flex items-center gap-2 px-3 py-2 bg-gradient-to-r from-brand-600 to-purple-600 text-white">
        <span class="text-lg">{{ settings.ballIconUrl ? '🤖' : settings.ballIcon }}</span>
        <span class="font-semibold text-sm flex-1">AI 助手</span>
        <button class="w-6 h-6 rounded-lg hover:bg-white/20 text-xs" title="对话/设置" @click="tab = tab === 'chat' ? 'settings' : 'chat'">
          {{ tab === 'chat' ? '⚙️' : '💬' }}
        </button>
        <button class="w-6 h-6 rounded-lg hover:bg-white/20 text-xs" title="隐藏助手（可从小图标找回）" @click="hideBall">🗕</button>
        <button class="w-6 h-6 rounded-lg hover:bg-white/20 text-xs" title="关闭" @click="open = false">✕</button>
      </div>

      <!-- 对话 -->
      <template v-if="tab === 'chat'">
        <div ref="listRef" class="taot-assistant-msgs flex-1 overflow-y-auto p-3 space-y-3 text-sm">
          <div v-for="(m, i) in messages" :key="i" class="flex" :class="m.role === 'user' ? 'justify-end' : 'justify-start'">
            <div
              class="taot-assistant-msg max-w-[85%] px-3 py-2 rounded-2xl whitespace-pre-wrap leading-relaxed"
              :class="m.role === 'user' ? 'bg-brand-500 text-white rounded-br-sm' : 'bg-white border border-slate-200 text-slate-700 rounded-bl-sm'"
            >{{ m.content }}</div>
          </div>
          <div v-if="busy" class="text-xs text-slate-400 pl-1">正在思考…</div>
          <p v-if="error" class="text-xs text-red-500 bg-red-50 px-3 py-2 rounded-lg">{{ error }}</p>

          <!-- RAG 来源 -->
          <div v-if="ragSources.length" class="space-y-1">
            <div class="text-[11px] text-slate-400">参考来源</div>
            <button
              v-for="(s, i) in ragSources.slice(0, 4)"
              :key="i"
              class="w-full text-left px-3 py-1.5 rounded-lg bg-brand-50 text-brand-700 text-xs hover:bg-brand-100 truncate"
              @click="openSource(s)"
            >
              📄 {{ s.title }}{{ s.heading_path ? ' · ' + s.heading_path : '' }}
            </button>
          </div>
        </div>

        <div class="p-2 border-t border-slate-100 flex gap-2 items-end bg-white/70">
          <textarea
            v-model="input"
            rows="1"
            class="taot-assistant-input flex-1 resize-none px-3 py-2 rounded-xl border border-slate-200 text-sm outline-none focus:border-brand-400 max-h-28"
            placeholder="输入问题，Enter 发送…"
            @keydown.enter.exact.prevent="send"
          />
          <button class="taot-assistant-send px-3 py-2 rounded-xl bg-brand-600 text-white text-sm disabled:opacity-40" :disabled="busy" @click="send">发送</button>
        </div>
      </template>

      <!-- 设置 -->
      <div v-else class="flex-1 overflow-y-auto p-3 space-y-4 text-sm bg-white">
        <section class="space-y-2">
          <h4 class="text-xs font-semibold text-slate-400">悬浮球外观</h4>
          <div class="grid grid-cols-2 gap-2">
            <label class="text-xs text-slate-500 flex flex-col gap-1">尺寸(px)<input v-model.number="settings.size" type="number" min="36" max="120" class="field" /></label>
            <label class="text-xs text-slate-500 flex flex-col gap-1">图标(emoji)<input v-model="settings.ballIcon" class="field" /></label>
            <label class="text-xs text-slate-500 flex flex-col gap-1">背景(颜色/渐变)<input v-model="settings.ballBg" class="field" /></label>
            <label class="text-xs text-slate-500 flex flex-col gap-1">图标图片URL<input v-model="settings.ballIconUrl" class="field" placeholder="留空用 emoji" /></label>
            <label class="text-xs text-slate-500 col-span-2 flex flex-col gap-1">问候语<input v-model="settings.greeting" class="field" /></label>
          </div>
        </section>

        <section class="space-y-2">
          <h4 class="text-xs font-semibold text-slate-400">聊天外观</h4>
          <label class="text-xs text-slate-500 flex flex-col gap-1">面板背景(颜色/图片URL/渐变)<input v-model="settings.panelBg" class="field" placeholder="留空默认" /></label>
        </section>

        <section class="space-y-2">
          <h4 class="text-xs font-semibold text-slate-400">LLM 对话配置</h4>
          <label class="text-xs text-slate-500 flex flex-col gap-1">对话方式
            <select v-model="settings.mode" class="field">
              <option value="chat">自由对话（通用模型）</option>
              <option value="rag">知识库问答（需配置后端 Embedding/LLM）</option>
            </select>
          </label>
          <label class="text-xs text-slate-500 flex flex-col gap-1">Base URL（留空用 .env LLM_BASE_URL）<input v-model="settings.llm.base_url" class="field" placeholder="https://api.deepseek.com/v1" /></label>
          <label class="text-xs text-slate-500 flex flex-col gap-1">API Key（浏览器本地保存，随请求转发；勿公开仓库）<input v-model="settings.llm.api_key" type="password" class="field" placeholder="sk-…" /></label>
          <label class="text-xs text-slate-500 flex flex-col gap-1">Model<input v-model="settings.llm.model" class="field" placeholder="deepseek-chat" /></label>
          <label class="text-xs text-slate-500 flex flex-col gap-1">System Prompt<textarea v-model="settings.llm.system" rows="2" class="field resize-none" /></label>
        </section>

        <section class="space-y-2">
          <h4 class="text-xs font-semibold text-slate-400">动态 DIY（高级）</h4>
          <p class="text-[11px] text-slate-400 leading-relaxed">
            使用类名 <code>.taot-assistant-ball/.panel/.head/.msgs/.msg/.input/.send/.mini</code> 自定义样式与动效。
          </p>
          <label class="text-xs text-slate-500 flex flex-col gap-1">自定义 CSS
            <textarea v-model="settings.customCss" rows="6" class="field resize-none font-mono text-[11px]" spellcheck="false"
              placeholder=".taot-assistant-msgs { background: #f8fafc; }
.taot-assistant-ball { animation: pulse 2s infinite; }" /></label>
          <label class="text-xs text-slate-500 flex flex-col gap-1">自定义 JS（window 作用域，本地运行）
            <textarea v-model="settings.customJs" rows="5" class="field resize-none font-mono text-[11px]" spellcheck="false"
              placeholder="setInterval(() => { document.querySelector('.taot-assistant-ball')?.classList.toggle('hidden') }, 3000);" /></label>
          <div class="flex gap-2 pt-1">
            <button class="flex-1 px-3 py-2 rounded-xl bg-brand-600 text-white text-sm" @click="applyDiy">应用</button>
            <button class="flex-1 px-3 py-2 rounded-xl bg-slate-200 text-slate-600 text-sm" @click="resetDiy">恢复默认</button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style>
.field { @apply w-full px-2.5 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-sm outline-none focus:border-brand-400; }
</style>
