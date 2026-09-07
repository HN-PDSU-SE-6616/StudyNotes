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

/** 流式对话：SSE 逐字回调；返回累计文本。异常走 onError（含服务端 error 事件）。 */
export async function streamAssistantChat(
  messages: ChatMsg[],
  overrides: ChatOverrides = {},
  onDelta?: (delta: string) => void,
): Promise<string> {
  const token = localStorage.getItem('access_token')
  const resp = await fetch('/api/v1/assistant/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      messages,
      base_url: overrides.base_url || null,
      api_key: overrides.api_key || null,
      model: overrides.model || null,
      temperature: overrides.temperature ?? 0.7,
      system: overrides.system || null,
    }),
  })
  if (!resp.ok || !resp.body) {
    let msg = `请求失败 (${resp.status})`
    try {
      const err = await resp.json()
      if (err.detail) msg = err.detail
    } catch { /* ignore */ }
    throw new Error(msg)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let acc = ''
  let errorMsg = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx: number
    while ((idx = buffer.indexOf('\n\n')) >= 0) {
      const raw = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      for (const line of raw.split('\n')) {
        if (!line.startsWith('data:')) continue
        const data = line.slice(5).trim()
        if (!data) continue
        if (data === '[DONE]') break
        try {
          const evt = JSON.parse(data)
          if (typeof evt.error === 'string' && evt.error) {
            errorMsg = evt.error
          } else if (typeof evt.delta === 'string' && evt.delta) {
            acc += evt.delta
            onDelta?.(evt.delta)
          }
        } catch { /* 忽略无法解析的事件 */ }
      }
    }
  }
  if (errorMsg) throw new Error(errorMsg)
  return acc
}
