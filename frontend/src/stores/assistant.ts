import { reactive, watch } from 'vue'

export interface AssistantSettings {
  visible: boolean        // 悬浮球显示开关（隐藏后可从小图标重新唤起）
  size: number            // 悬浮球尺寸 px
  ballBg: string
  ballIcon: string        // emoji 或文本
  ballIconUrl: string     // 自定义图片 URL（优先级高于 emoji）
  greeting: string
  panelBg: string         // 聊天面板背景
  mode: 'chat' | 'rag'    // 对话方式：自由对话 / 知识库问答
  llm: {
    base_url: string
    api_key: string
    model: string
    temperature: number
    system: string
  }
  customCss: string
  customJs: string
}

const STORAGE_KEY = 'taot.assistant.v1'

export const DEFAULT_SETTINGS: AssistantSettings = {
  visible: true,
  size: 54,
  ballBg: 'linear-gradient(135deg,#6366f1,#a855f7)',
  ballIcon: '🤖',
  ballIconUrl: '',
  greeting: '你好呀 👋 我是你的 AI 助手，想问点什么？',
  panelBg: '',
  mode: 'chat',
  llm: {
    base_url: '',
    api_key: '',
    model: '',
    temperature: 0.7,
    system: '你是一位乐于助人的 AI 助手。回答请简洁、准确。',
  },
  customCss: '',
  customJs: '',
}

function load(): AssistantSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        ...DEFAULT_SETTINGS,
        ...parsed,
        llm: { ...DEFAULT_SETTINGS.llm, ...(parsed.llm || {}) },
      }
    }
  } catch {
    // 忽略损坏配置
  }
  return { ...DEFAULT_SETTINGS, llm: { ...DEFAULT_SETTINGS.llm } }
}

const settings = reactive<AssistantSettings>(load())

watch(settings, () => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch {
    // 存储满时忽略
  }
}, { deep: true })

/** 注入自定义 CSS（以 <style> 标签形式作用于 .taot-assistant-* 选择器） */
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

/** 执行自定义 JS（本地 DIY 代码；在 window 作用域执行） */
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
