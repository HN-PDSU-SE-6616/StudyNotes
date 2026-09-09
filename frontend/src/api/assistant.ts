import api from './index'

export interface ChatMsg {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface PlanStep {
  goal: string
  summary?: string
}

export interface ChatOverrides {
  session_id?: string | null
  system?: string | null
  temperature?: number
  tools?: boolean
  mode?: string // auto | simple | plan（后端计划层开关）
  client_context?: Record<string, string> | null
  project_id?: string | null
}

export interface ChatResult {
  reply: string
  model: string
  cached?: boolean
  used_tools?: boolean
  steps?: PlanStep[]
}

export const assistantApi = {
  /** AI 对话（Agent：计划层 + 工具 + 上下文感知缓存；模型由后端 .env 配置） */
  chat: (messages: ChatMsg[], overrides: ChatOverrides = {}) =>
    api.post<ChatResult>(
      '/assistant/chat',
      {
        messages,
        session_id: overrides.session_id || null,
        system: overrides.system || null,
        temperature: overrides.temperature ?? 0.7,
        tools: overrides.tools ?? true,
        mode: overrides.mode || 'auto',
        client_context: overrides.client_context || null,
        project_id: overrides.project_id || null,
      },
    ),
  /** 清空指定会话的服务端上下文（session_id） */
  clearContext: (sessionId: string) =>
    api.post<{ ok: boolean }>('/assistant/context/clear', { session_id: sessionId }),
}

/** 流式对话：SSE 逐字回调（计划层/工具/缓存/会话与 /chat 一致）。
 * 服务端先可能下发 steps 事件（onPlan），再逐字 delta；异常走 onError。 */
export async function streamAssistantChat(
  messages: ChatMsg[],
  overrides: ChatOverrides = {},
  onDelta?: (delta: string) => void,
  onPlan?: (steps: PlanStep[]) => void,
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
      session_id: overrides.session_id || null,
      system: overrides.system || null,
      temperature: overrides.temperature ?? 0.7,
      tools: overrides.tools ?? true,
      mode: overrides.mode || 'auto',
      client_context: overrides.client_context || null,
      project_id: overrides.project_id || null,
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
          } else if (Array.isArray(evt.steps)) {
            onPlan?.(evt.steps as PlanStep[])
          }
        } catch { /* 忽略无法解析的事件 */ }
      }
    }
  }
  if (errorMsg) throw new Error(errorMsg)
  return acc
}
