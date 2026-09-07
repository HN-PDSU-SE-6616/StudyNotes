import api from './index'

export interface ChatMsg {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface ChatOverrides {
  base_url?: string | null
  api_key?: string | null
  model?: string | null
  temperature?: number
  system?: string | null
}

export const assistantApi = {
  /** 自由对话（OpenAI 兼容，经后端代理转发；配置可覆盖后端默认） */
  chat: (messages: ChatMsg[], overrides: ChatOverrides = {}) =>
    api.post<{ reply: string; model: string }>('/assistant/chat', {
      messages,
      base_url: overrides.base_url || null,
      api_key: overrides.api_key || null,
      model: overrides.model || null,
      temperature: overrides.temperature ?? 0.7,
      system: overrides.system || null,
    }),
}
