import { reactive, watch } from 'vue'

/**
 * AI 助手外观/对话设置（浏览器本地持久化）
 *
 * 设计约定（本轮需求）：
 * - 模型相关配置（base_url/api_key/model）移除 —— 统一由后端 .env 管理；
 * - 内置浅色/深色（黑白）主题；悬浮球/面板背景默认实体不透明；
 * - 图标支持预设 emoji 或本地上传图片（dataURL）；
 * - 多用选项/滑块，少文本框；各配置默认值在面板中可见；
 * - 默认内置一组动态特效（effectOn=true, float），可开关与换风格。
 */
export interface AssistantSettings {
  visible: boolean
  size: number
  theme: 'light' | 'dark'
  ballBg: string
  ballIcon: string
  ballIconUrl: string
  greeting: string
  panelBg: string
  mode: 'chat' | 'rag'
  effectOn: boolean
  effectType: 'float' | 'pulse' | 'glow' | 'none'
  temperature: number
  toolsEnabled: boolean
  system: string
  customCss: string
  customJs: string
}

export const PRESET_ICONS = ['🤖', '😺', '🌟', '🧠', '🦉', '🚀', '🎨', '✨']
export const BALL_BG_COLORS = [
  'linear-gradient(135deg,#6366f1,#a855f7)',
  'linear-gradient(135deg,#0ea5e9,#6366f1)',
  'linear-gradient(135deg,#f43f5e,#f97316)',
  'linear-gradient(135deg,#10b981,#0ea5e9)',
  'linear-gradient(135deg,#f59e0b,#ef4444)',
  'linear-gradient(135deg,#334155,#0f172a)',
  '#ec4899',
  '#8b5cf6',
]
export const PANEL_BG_CHOICES = [
  { label: '随主题（默认）', value: '' },
  { label: '磨砂白', value: 'rgba(255,255,255,0.97)' },
  { label: '深空渐变', value: 'linear-gradient(160deg,#0f172a,#1e293b)' },
  { label: '品牌渐变', value: 'linear-gradient(160deg,#eef2ff,#faf5ff)' },
]

const STORAGE_KEY = 'taot.assistant.v2'

export const DEFAULT_SETTINGS: AssistantSettings = {
  visible: true,
  size: 54,
  theme: 'light',
  ballBg: 'linear-gradient(135deg,#6366f1,#a855f7)',
  ballIcon: '🤖',
  ballIconUrl: '',
  greeting: '你好呀 👋 我是你的 AI 助手，想问点什么？',
  panelBg: '',
  mode: 'chat',
  effectOn: true,
  effectType: 'float',
  temperature: 0.7,
  toolsEnabled: true,
  system: '你是一位乐于助人的 AI 助手。回答请简洁、准确，需要实时/外部信息时使用工具。',
  customCss: '',
  customJs: '',
}

function load(): AssistantSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      // 兼容 v1：丢弃旧 llm 覆盖配置，其余字段合入默认值
      const { llm: _drop, ...rest } = parsed || {}
      return { ...DEFAULT_SETTINGS, ...rest }
    }
  } catch {
    // 忽略损坏配置
  }
  return { ...DEFAULT_SETTINGS }
}

const settings = reactive<AssistantSettings>(load())

watch(settings, () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // 存储满时忽略
  }
}, { deep: true })

/** 注入自定义 CSS（作用于 .taot-assistant-* 选择器） */
export function applyCustomCss(css: string) {
  let el = document.getElementById('taot-assistant-style') as HTMLStyleElement | null
  if (!css.trim()) {
    el?.remove()
    return
  }
  if (!el) {
    el = document.createElement('style')
    el.id = 'taot-assistant-style'
    document.head.appendChild(el)
  }
  el.textContent = css
}

/** 执行自定义 JS（本地 DIY，window 作用域） */
export function runCustomJs(js: string) {
  if (!js.trim()) return
  try {
    const fn = new Function('window', 'document', `"use strict";\n${js}`)
    fn(window, document)
  } catch (err) {
    console.error('[Assistant DIY] 自定义 JS 执行失败', err)
  }
}

export function useAssistantStore() {
  return { settings, applyCustomCss, runCustomJs }
}
