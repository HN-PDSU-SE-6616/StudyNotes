/**
 * 浏览器端环境信息采集（供 AI 助手 get_system_info(scope=client) 使用）
 * 在 mounted 后调用，所有字段尽力而为、失败静默。
 */
export interface ClientInfo {
  os: string
  browser: string
  platform: string
  cores: string
  memory: string
  gpu: string
  lang: string
  screen: string
}

function detectOs(ua: string): string {
  if (/Windows NT 10/.test(ua)) return 'Windows 10/11'
  if (/Windows NT 6\.3/.test(ua)) return 'Windows 8.1'
  if (/Mac OS X/.test(ua)) return 'macOS'
  if (/Android/.test(ua)) return 'Android'
  if (/iPhone|iPad/.test(ua)) return 'iOS'
  if (/Linux/.test(ua)) return 'Linux'
  return ua
}

function detectBrowser(ua: string): string {
  if (/Edg\//.test(ua)) return 'Edge'
  if (/Chrome\//.test(ua)) return 'Chrome'
  if (/Firefox\//.test(ua)) return 'Firefox'
  if (/Safari\//.test(ua)) return 'Safari'
  return '未知'
}

function detectGpu(): string {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl')
    if (!gl) return ''
    const dbg = gl.getExtension('WEBGL_debug_renderer_info')
    if (!dbg) return 'WebGL（无渲染器信息）'
    const name = String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || '')
    return name || 'WebGL'
  } catch {
    return ''
  }
}

export function detectClientInfo(): ClientInfo {
  const ua = navigator.userAgent || ''
  const nav = navigator as Navigator & { deviceMemory?: number }
  let gpu = ''
  try {
    gpu = detectGpu()
  } catch { /* 忽略 */ }
  return {
    os: detectOs(ua),
    browser: detectBrowser(ua),
    platform: (navigator as unknown as { platform?: string }).platform || '',
    cores: String(navigator.hardwareConcurrency || ''),
    memory: nav.deviceMemory ? String(nav.deviceMemory) : '',
    gpu,
    lang: navigator.language || '',
    screen: `${window.screen?.width || 0}×${window.screen?.height || 0}`,
  }
}
