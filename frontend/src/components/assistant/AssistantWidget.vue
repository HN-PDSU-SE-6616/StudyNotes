<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { assistantApi, streamAssistantChat, type ChatMsg } from '@/api/assistant'
import { ragApi } from '@/api/files'
import { useAssistantStore, PRESET_ICONS, BALL_BG_COLORS, PANEL_BG_CHOICES } from '@/stores/assistant'
import { useOrgStore } from '@/stores/org'
import { renderAssistantMarkdown } from '@/utils/markdown'
import { detectClientInfo, type ClientInfo } from '@/utils/clientInfo'
import type { RagSource } from '@/types'

const { settings, applyCustomCss, runCustomJs } = useAssistantStore()
const orgStore = useOrgStore()
const router = useRouter()

const open = ref(false)
const tab = ref<'chat' | 'settings'>('chat')
const busy = ref(false)
const error = ref('')
const messages = ref<ChatMsg[]>([{ role: 'assistant', content: settings.greeting }])
const input = ref('')
const ragSources = ref<RagSource[]>([])
const listRef = ref<HTMLDivElement>()
const iconFile = ref<HTMLInputElement>()

// 会话：固定 session_id（清空上下文后重置），服务端按用户记忆最近对话
const SESSION_KEY = 'taot.assistant.session'
const sessionId = ref(localStorage.getItem(SESSION_KEY) || `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`)
let clientInfo: ClientInfo | null = null

const ballStyle = computed(() => ({
  width: `${settings.size}px`,
  height: `${settings.size}px`,
  background: settings.ballBg || 'linear-gradient(135deg,#6366f1,#a855f7)',
  fontSize: `${Math.max(16, settings.size * 0.52)}px`,
}))
const panelVars = computed(() => ({
  '--ap-bg': settings.panelBg || (settings.theme === 'dark' ? '#111827' : '#ffffff'),
  '--ap-text': settings.theme === 'dark' ? '#e5e7eb' : '#1f2937',
  '--ap-sub': settings.theme === 'dark' ? '#9ca3af' : '#64748b',
  '--ap-bubble': settings.theme === 'dark' ? '#1f2937' : '#ffffff',
  '--ap-bubble-line': settings.theme === 'dark' ? '#374151' : '#e2e8f0',
  '--ap-input': settings.theme === 'dark' ? '#1f2937' : '#ffffff',
  '--ap-panel-border': settings.theme === 'dark' ? '#374151' : '#e2e8f0',
} as Record<string, string>))
const effectClass = computed(() => (settings.effectOn ? `taot-effect-${settings.effectType}` : ''))
const themeClass = computed(() => `theme-${settings.theme}`)

function saveSession() {
  localStorage.setItem(SESSION_KEY, sessionId.value)
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
  const lastIdx = messages.value.length
  try {
    if (settings.mode === 'rag') {
      const pid = orgStore.activeProject?.id ?? null
      const { data } = await ragApi.ask(text, pid, 6)
      messages.value.push({ role: 'assistant', content: data.answer || '（无回答）' })
      ragSources.value = data.sources || []
      return
    }
    // 自由对话：服务端会话记忆（只传本轮问题）+ 工具 + 浏览器环境
    messages.value.push({ role: 'assistant', content: '' })
    const reply = await streamAssistantChat(
      [{ role: 'user', content: text }],
      {
        session_id: sessionId.value,
        system: settings.system,
        temperature: settings.temperature,
        tools: settings.toolsEnabled,
        client_context: clientInfo as unknown as Record<string, string>,
      },
      (delta) => {
        messages.value[lastIdx].content += delta
        scrollBottom()
      },
    )
    if (!messages.value[lastIdx].content && reply) messages.value[lastIdx].content = reply
    if (!messages.value[lastIdx].content) messages.value[lastIdx].content = '（空回复）'
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string } } }
    error.value = err.response?.data?.detail || '请求失败：请检查后端 LLM/工具配置或网络'
  } finally {
    busy.value = false
    scrollBottom()
  }
}

/** 消息气泡渲染：流式中保护未闭合代码围栏，完成后完整渲染 markdown */
function bubbleHtml(m: ChatMsg): string {
  if (m.role === 'user') return ''
  const streaming = busy.value && messages.value[messages.value.length - 1] === m
  return renderAssistantMarkdown(m.content || '', streaming)
}

async function clearChat() {
  if (window.confirm('清空当前对话上下文？助手将不再记得此前的问答。')) {
    messages.value = [{ role: 'assistant', content: settings.greeting }]
    sessionId.value = `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
    saveSession()
    try { await assistantApi.clearContext(sessionId.value) } catch { /* 后端不可达时仅本地清空 */ }
  }
}

function onPickIcon(icon: string) {
  settings.ballIcon = icon
  settings.ballIconUrl = ''
}

function onIconUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (file.size > 1_500_000) {
    alert('图标图片请控制在 1.5MB 以内')
    return
  }
  const reader = new FileReader()
  reader.onload = () => {
    settings.ballIconUrl = String(reader.result || '')
    settings.ballIcon = PRESET_ICONS[0]
  }
  reader.readAsDataURL(file)
  input.value = ''
}

function applyDiy() {
  applyCustomCss(settings.customCss)
  runCustomJs(settings.customJs)
  alert('已应用外观配置与自定义 CSS/JS')
}

function resetDiy() {
  const cur = {
    visible: settings.visible, mode: settings.mode,
    llm: undefined as unknown, // 兼容旧存储引用（不读取）
  }
  Object.assign(settings, {
    visible: cur.visible,
    size: 54,
    theme: 'light',
    ballBg: BALL_BG_COLORS[0],
    ballIcon: '🤖',
    ballIconUrl: '',
    greeting: '你好呀 👋 我是你的 AI 助手，想问点什么？',
    panelBg: '',
    mode: cur.mode,
    effectOn: true,
    effectType: 'float',
    temperature: 0.7,
    toolsEnabled: true,
    system: '你是一位乐于助人的 AI 助手。回答请简洁、准确，需要实时/外部信息时使用工具。',
    customCss: '',
    customJs: '',
  })
  applyCustomCss('')
}

function hideBall() {
  settings.visible = false
  open.value = false
}

function reveal() {
  settings.visible = true
  open.value = true
  tab.value = 'settings'
}

function openSource(src: RagSource) {
  open.value = false
  router.push({ path: `/notes/${src.slug}`, query: { project: src.project_id, anchor: src.heading_path || '' } })
}

onMounted(() => {
  saveSession()
  clientInfo = detectClientInfo()
  if (settings.visible) applyCustomCss(settings.customCss)
})
</script>

<template>
  <div>
    <!-- 迷你条：球被隐藏时的重显入口 -->
    <div
      v-if="!settings.visible"
      class="fixed bottom-5 right-4 z-[9990] px-2 py-1 rounded-full bg-slate-800/80 text-white text-[11px] cursor-pointer select-none"
      title="显示 AI 助手"
      @click="reveal"
    >
      {{ settings.ballIcon || '🤖' }} AI 助手已隐藏 · 点击设置
    </div>

    <!-- 悬浮球（默认内置漂浮/呼吸动态特效，可在设置关闭） -->
    <button
      v-else
      class="taot-assistant-ball ap-ball"
      :class="effectClass"
      :style="ballStyle"
      title="AI 助手"
      @click="open = !open"
    >
      <img v-if="settings.ballIconUrl" :src="settings.ballIconUrl" class="ap-ball-icon" alt="assistant" />
      <span v-else>{{ settings.ballIcon }}</span>
    </button>

    <!-- 助手面板 -->
    <div
      v-if="open"
      class="taot-assistant-panel ap-panel"
      :class="[themeClass, { 'taot-effect-glow-panel': settings.effectOn && settings.effectType === 'glow' }]"
      :style="panelVars"
    >
      <div class="ap-head">
        <span class="ap-head-icon">{{ settings.ballIconUrl ? '🤖' : settings.ballIcon }}</span>
        <span class="ap-head-title">AI 助手</span>
        <button class="ap-head-btn" title="清空上下文" @click="clearChat">🗑</button>
        <button class="ap-head-btn" :title="tab === 'chat' ? '设置' : '对话'" @click="tab = tab === 'chat' ? 'settings' : 'chat'">
          {{ tab === 'chat' ? '⚙️' : '💬' }}
        </button>
        <button class="ap-head-btn" title="隐藏助手（可从小图标找回）" @click="hideBall">🗕</button>
        <button class="ap-head-btn" title="关闭" @click="open = false">✕</button>
      </div>

      <!-- 对话 -->
      <template v-if="tab === 'chat'">
        <div ref="listRef" class="taot-assistant-msgs ap-msgs">
          <div v-for="(m, i) in messages" :key="i" class="ap-row" :class="m.role === 'user' ? 'ap-row-user' : 'ap-row-bot'">
            <div v-if="m.role === 'user'" class="taot-assistant-msg ap-bubble ap-bubble-user">{{ m.content }}</div>
            <div
              v-else
              class="taot-assistant-msg ap-bubble ap-bubble-bot taot-md-body"
              v-html="bubbleHtml(m)"
            />
          </div>
          <div v-if="busy" class="ap-hint">正在思考…</div>
          <p v-if="error" class="ap-error">{{ error }}</p>

          <!-- RAG 来源 -->
          <div v-if="ragSources.length" class="space-y-1">
            <div class="ap-hint">参考来源</div>
            <button
              v-for="(s, i) in ragSources.slice(0, 4)"
              :key="i"
              class="ap-source"
              @click="openSource(s)"
            >
              📄 {{ s.title }}{{ s.heading_path ? ' · ' + s.heading_path : '' }}
            </button>
          </div>
        </div>

        <div class="ap-inputbar">
          <textarea
            v-model="input"
            rows="1"
            class="taot-assistant-input ap-input"
            placeholder="输入问题，Enter 发送…（可问天气/IP/系统信息等，需要时我会联网）"
            @keydown.enter.exact.prevent="send"
          />
          <button class="taot-assistant-send ap-send" :disabled="busy" @click="send">发送</button>
        </div>
      </template>

      <!-- 设置 -->
      <div v-else class="taot-assistant-settings ap-settings">
        <section class="ap-sec">
          <h4 class="ap-sec-title">悬浮球外观</h4>
          <label class="ap-label-row">
            <span>尺寸</span>
            <input v-model.number="settings.size" type="range" min="36" max="120" class="ap-range" />
            <b class="ap-val">{{ settings.size }}px</b>
          </label>
          <div class="ap-label">
            <span>图标</span>
            <div class="ap-icon-grid">
              <button
                v-for="ic in PRESET_ICONS"
                :key="ic"
                class="ap-icon-opt"
                :class="{ active: settings.ballIcon === ic && !settings.ballIconUrl }"
                @click="onPickIcon(ic)"
              >{{ ic }}</button>
            </div>
            <div class="ap-inline">
              <button class="ap-btn-soft" @click="iconFile?.click()">🖼 上传图片</button>
              <button v-if="settings.ballIconUrl" class="ap-btn-soft" @click="settings.ballIconUrl = ''">移除图片</button>
              <input ref="iconFile" type="file" accept="image/*" class="hidden" @change="onIconUpload" />
            </div>
          </div>
          <div class="ap-label">
            <span>球背景</span>
            <div class="ap-color-grid">
              <button
                v-for="bg in BALL_BG_COLORS"
                :key="bg"
                class="ap-color-opt"
                :class="{ active: settings.ballBg === bg }"
                :style="{ background: bg }"
                :title="bg"
                @click="settings.ballBg = bg"
              />
              <input v-model="settings.ballBg" type="color" class="ap-color-custom" title="自定义颜色" />
            </div>
          </div>
          <label class="ap-label">
            <span>问候语</span>
            <select v-model="settings.greeting" class="ap-input-sm">
              <option value="你好呀 👋 我是你的 AI 助手，想问点什么？">默认：你好呀 👋 想问点什么？</option>
              <option value="嗨！我是你的知识库助手，可以问我笔记问题或天气等实时信息。">活泼版：知识库助手打招呼</option>
              <option value="你好，随时为你解答。">简洁版：随时为你解答</option>
            </select>
          </label>
        </section>

        <section class="ap-sec">
          <h4 class="ap-sec-title">面板与对话</h4>
          <label class="ap-label-row">
            <span>主题</span>
            <div class="ap-seg">
              <button class="ap-seg-item" :class="{ active: settings.theme === 'light' }" @click="settings.theme = 'light'">☀️ 浅色</button>
              <button class="ap-seg-item" :class="{ active: settings.theme === 'dark' }" @click="settings.theme = 'dark'">🌙 深色</button>
            </div>
          </label>
          <label class="ap-label">
            <span>面板背景</span>
            <select v-model="settings.panelBg" class="ap-input-sm">
              <option v-for="ch in PANEL_BG_CHOICES" :key="ch.value" :value="ch.value">{{ ch.label }}</option>
            </select>
          </label>
          <label class="ap-label-row">
            <span>对话方式</span>
            <select v-model="settings.mode" class="ap-input-sm w-auto">
              <option value="chat">自由对话（通用模型）</option>
              <option value="rag">知识库问答（基于笔记，需后端 Embedding）</option>
            </select>
          </label>
          <label class="ap-label-row">
            <span>创造性</span>
            <input v-model.number="settings.temperature" type="range" min="0" max="1.5" step="0.1" class="ap-range" />
            <b class="ap-val">{{ Number(settings.temperature).toFixed(1) }}</b>
          </label>
          <label class="ap-label-row">
            <span>联网/实时工具</span>
            <input v-model="settings.toolsEnabled" type="checkbox" class="ap-check" />
            <span class="ap-val">天气 · IP · 系统 · 网页搜索</span>
          </label>
          <p class="ap-tip">模型与密钥由后端 <code>.env</code>（LLM_MODEL / LLM_API_KEY）统一配置，无需在此填写。</p>
        </section>

        <section class="ap-sec">
          <h4 class="ap-sec-title">动态特效（默认开启）</h4>
          <label class="ap-label-row">
            <span>启用特效</span>
            <input v-model="settings.effectOn" type="checkbox" class="ap-check" />
          </label>
          <label class="ap-label-row">
            <span>风格</span>
            <div class="ap-seg">
              <button class="ap-seg-item" :class="{ active: settings.effectType === 'float' }" @click="settings.effectType = 'float'">漂浮</button>
              <button class="ap-seg-item" :class="{ active: settings.effectType === 'pulse' }" @click="settings.effectType = 'pulse'">呼吸</button>
              <button class="ap-seg-item" :class="{ active: settings.effectType === 'glow' }" @click="settings.effectType = 'glow'">光晕</button>
              <button class="ap-seg-item" :class="{ active: settings.effectType === 'none' }" @click="settings.effectType = 'none'">无</button>
            </div>
          </label>
        </section>

        <section class="ap-sec">
          <h4 class="ap-sec-title">角色设定与高级 DIY</h4>
          <label class="ap-label">
            <span>System Prompt（默认已填）</span>
            <textarea v-model="settings.system" rows="2" class="ap-input-sm resize-none" />
          </label>
          <p class="ap-tip">自定义类名：<code>.taot-assistant-ball/.panel/.msgs/.msg/.input/.send</code></p>
          <label class="ap-label">
            <span>自定义 CSS（默认值示例已显示，可改写）</span>
            <textarea
              v-model="settings.customCss"
              rows="4"
              class="ap-input-sm resize-none font-mono text-[11px]"
              spellcheck="false"
              placeholder="/* 默认漂浮特效（你关闭后也可在此手动启用） */
.taot-assistant-ball { animation: ap-float 3.6s ease-in-out infinite; }
@keyframes ap-float { 0%,100%{ transform: translateY(0) } 50%{ transform: translateY(-8px) } }"
            />
          </label>
          <label class="ap-label">
            <span>自定义 JS（window 作用域）</span>
            <textarea
              v-model="settings.customJs"
              rows="3"
              class="ap-input-sm resize-none font-mono text-[11px]"
              spellcheck="false"
              placeholder="console.log('assistant ready')"
            />
          </label>
          <div class="ap-inline mt-2">
            <button class="ap-btn-primary" @click="applyDiy">应用外观</button>
            <button class="ap-btn-soft" @click="resetDiy">恢复默认</button>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style>
/* ============ 助手基础（白底不透明；深色主题走 CSS 变量） ============ */
.ap-ball {
  position: fixed;
  right: 1rem;
  bottom: 1.25rem;
  z-index: 9990;
  border-radius: 9999px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.25);
  cursor: pointer;
  border: none;
  transition: transform 0.15s ease;
}
.ap-ball:hover { transform: scale(1.08); }
.ap-ball-icon { width: 60%; height: 60%; object-fit: contain; border-radius: 9999px; }

.ap-panel {
  position: fixed;
  right: 1rem;
  bottom: 5.5rem;
  z-index: 9995;
  width: 390px;
  max-width: calc(100vw - 2rem);
  height: 580px;
  max-height: calc(100vh - 7rem);
  border-radius: 1.25rem;
  box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.3);
  border: 1px solid var(--ap-panel-border);
  background: var(--ap-bg);
  color: var(--ap-text);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-size: 14px;
}

.ap-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: linear-gradient(135deg, #6366f1, #a855f7);
  color: #fff;
  flex-shrink: 0;
}
.ap-head-icon { font-size: 18px; }
.ap-head-title { font-weight: 600; flex: 1; }
.ap-head-btn {
  width: 26px; height: 26px; border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255, 255, 255, 0.12); border: none; color: #fff;
  font-size: 12px; cursor: pointer;
}
.ap-head-btn:hover { background: rgba(255, 255, 255, 0.28); }

.ap-msgs {
  flex: 1; overflow-y: auto; padding: 0.75rem;
  display: flex; flex-direction: column; gap: 0.6rem;
  background: var(--ap-bg);
}
.ap-row { display: flex; }
.ap-row-user { justify-content: flex-end; }
.ap-row-bot { justify-content: flex-start; }
.ap-bubble {
  max-width: 86%; padding: 0.5rem 0.75rem; border-radius: 1rem;
  line-height: 1.6; word-break: break-word;
}
.ap-bubble-user {
  background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff;
  border-bottom-right-radius: 4px; white-space: pre-wrap;
}
.ap-bubble-bot {
  background: var(--ap-bubble); border: 1px solid var(--ap-bubble-line);
  border-bottom-left-radius: 4px;
}
.ap-hint { color: var(--ap-sub); font-size: 12px; padding-left: 4px; }
.ap-error { color: #ef4444; background: rgba(239, 68, 68, 0.1); padding: 6px 10px; border-radius: 8px; font-size: 12px; }
.ap-source {
  width: 100%; text-align: left; padding: 6px 10px; border-radius: 8px;
  background: rgba(99, 102, 241, 0.08); color: var(--ap-text);
  font-size: 12px; cursor: pointer; border: none; margin-top: 2px;
}
.ap-source:hover { background: rgba(99, 102, 241, 0.16); }

.ap-inputbar {
  display: flex; gap: 0.5rem; align-items: flex-end;
  padding: 0.5rem; border-top: 1px solid var(--ap-panel-border);
  background: var(--ap-bg); flex-shrink: 0;
}
.ap-input {
  flex: 1; resize: none; padding: 8px 10px; border-radius: 12px;
  border: 1px solid var(--ap-bubble-line); background: var(--ap-input);
  color: var(--ap-text); outline: none; font-size: 14px; max-height: 7rem;
}
.ap-input:focus { border-color: #818cf8; }
.ap-send {
  padding: 8px 14px; border-radius: 12px; background: #6366f1; color: #fff;
  border: none; cursor: pointer; font-size: 14px;
}
.ap-send:disabled { opacity: 0.4; }

/* ============ 设置面板 ============ */
.ap-settings { flex: 1; overflow-y: auto; padding: 0.75rem; display: flex; flex-direction: column; gap: 0.9rem; background: var(--ap-bg); }
.ap-sec { display: flex; flex-direction: column; gap: 0.5rem; }
.ap-sec-title { font-size: 12px; font-weight: 600; color: var(--ap-sub); margin: 0; }
.ap-label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--ap-sub); }
.ap-label-row { display: flex; align-items: center; gap: 0.5rem; font-size: 12px; color: var(--ap-sub); }
.ap-val { color: var(--ap-text); font-weight: 500; }
.ap-range { flex: 1; accent-color: #6366f1; }
.ap-check { accent-color: #6366f1; width: 16px; height: 16px; }
.ap-input-sm, .ap-input-sm option {
  padding: 6px 8px; border-radius: 8px; border: 1px solid var(--ap-bubble-line);
  background: var(--ap-input); color: var(--ap-text); font-size: 13px; outline: none;
}
.ap-input-sm option { background: var(--ap-input); }
.w-auto { width: auto; }

.ap-icon-grid { display: flex; flex-wrap: wrap; gap: 4px; }
.ap-icon-opt {
  width: 34px; height: 34px; font-size: 18px; border-radius: 10px;
  border: 1px solid var(--ap-bubble-line); background: var(--ap-input); cursor: pointer;
}
.ap-icon-opt.active { border-color: #6366f1; background: rgba(99, 102, 241, 0.15); }

.ap-color-grid { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.ap-color-opt {
  width: 26px; height: 26px; border-radius: 8px; border: 2px solid var(--ap-panel-border); cursor: pointer;
}
.ap-color-opt.active { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.3); }
.ap-color-custom { width: 30px; height: 30px; border: none; background: none; cursor: pointer; }

.ap-seg { display: inline-flex; border: 1px solid var(--ap-bubble-line); border-radius: 10px; overflow: hidden; }
.ap-seg-item {
  padding: 4px 10px; font-size: 12px; border: none; cursor: pointer;
  background: var(--ap-input); color: var(--ap-sub);
}
.ap-seg-item.active { background: #6366f1; color: #fff; }

.ap-inline { display: flex; gap: 8px; align-items: center; }
.ap-btn-primary {
  padding: 7px 14px; border-radius: 10px; background: #6366f1; color: #fff; border: none; cursor: pointer; font-size: 13px;
}
.ap-btn-soft {
  padding: 6px 12px; border-radius: 10px; background: var(--ap-input);
  border: 1px solid var(--ap-bubble-line); color: var(--ap-text); cursor: pointer; font-size: 12px;
}
.ap-btn-soft:hover { border-color: #818cf8; }
.ap-tip { font-size: 11px; color: var(--ap-sub); line-height: 1.5; margin: 0; }
.ap-tip code { background: rgba(99, 102, 241, 0.1); padding: 1px 4px; border-radius: 4px; }

/* ============ Markdown 内容 ============ */
.taot-md-body > :first-child { margin-top: 0; }
.taot-md-body > :last-child { margin-bottom: 0; }
.taot-md-body p { margin: 0.35em 0; }
.taot-md-body strong { font-weight: 700; }
.taot-md-body em { font-style: italic; }
.taot-md-body ul { list-style: disc; padding-left: 1.2em; margin: 0.35em 0; }
.taot-md-body ol { list-style: decimal; padding-left: 1.3em; margin: 0.35em 0; }
.taot-md-body li { margin: 0.15em 0; }
.taot-md-body h1, .taot-md-body h2, .taot-md-body h3 { margin: 0.6em 0 0.25em; font-weight: 700; line-height: 1.3; }
.taot-md-body h1 { font-size: 1.25em; } .taot-md-body h2 { font-size: 1.15em; } .taot-md-body h3 { font-size: 1.05em; }
.taot-md-body blockquote { border-left: 3px solid #a5b4fc; padding-left: 0.6em; margin: 0.4em 0; color: var(--ap-sub); }
.taot-md-body a { color: #818cf8; text-decoration: underline; }
.taot-md-body code {
  background: rgba(99, 102, 241, 0.12); border-radius: 4px; padding: 1px 5px; font-size: 0.9em;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.taot-md-body pre {
  background: #0b1220; color: #e2e8f0; border-radius: 10px; padding: 0.6em 0.8em;
  overflow-x: auto; margin: 0.5em 0;
}
.taot-md-body pre code { background: none; padding: 0; color: inherit; }
.taot-md-body table { border-collapse: collapse; margin: 0.5em 0; font-size: 0.92em; }
.taot-md-body th, .taot-md-body td { border: 1px solid var(--ap-bubble-line); padding: 3px 8px; }
.taot-md-body hr { border: none; border-top: 1px solid var(--ap-bubble-line); margin: 0.6em 0; }
.taot-md-code-streaming { white-space: pre-wrap; }

/* ============ 内置默认动态特效 ============ */
@keyframes ap-float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-9px); } }
@keyframes ap-pulse { 0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.45); } 70% { box-shadow: 0 0 0 14px rgba(99, 102, 241, 0); } }
@keyframes ap-glow { 0%, 100% { filter: drop-shadow(0 0 2px rgba(168, 85, 247, 0.5)); } 50% { filter: drop-shadow(0 0 14px rgba(168, 85, 247, 0.9)); } }
.taot-effect-float { animation: ap-float 3.8s ease-in-out infinite; }
.taot-effect-pulse { animation: ap-pulse 2.4s ease-out infinite; }
.taot-effect-glow { animation: ap-glow 2.8s ease-in-out infinite; }
.taot-effect-glow-panel { box-shadow: 0 25px 50px -12px rgba(168, 85, 247, 0.35); }
</style>
