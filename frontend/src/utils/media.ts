/**
 * 媒体 URL 工具：给受保护的文件访问 URL 附带 access_token 查询参数
 *
 * 背景：<img> 等媒体标签无法携带 Authorization 请求头，后端媒体接口
 * （/api/v1/files/.../content）支持 ?access_token= 鉴权，渲染时统一在此附加。
 * 非本站文件（外链/dataURL）原样返回。
 */
export function mediaUrl(url?: string | null): string {
  if (!url) return ''
  const raw = String(url)
  if (!raw.startsWith('/api/v1/files/')) return raw
  const token = localStorage.getItem('access_token')
  if (!token) return raw
  const sep = raw.includes('?') ? '&' : '?'
  return `${raw}${sep}access_token=${encodeURIComponent(token)}`
}
