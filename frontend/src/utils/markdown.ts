/**
 * Markdown 渲染工具（AI 助手消息展示用）
 *
 * - 完整渲染：marked → DOMPurify 消毒（粗体/列表/引用/代码块/表格等）；
 * - 流式中转：未闭合的 ``` 代码围栏不交给 marked（避免中间态花屏），
 *   尾部开放式内容以纯文本 <pre> 呈现，闭合后下一次渲染自动合并为代码块。
 */
import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: true })

const FENCE_RE = /```/g

/** 切分文本：([已闭合部分, 未闭合尾部], 是否有未闭合围栏) */
function splitOpenFence(md: string): { head: string; tail: string; open: boolean } {
  const idxs: number[] = []
  let m: RegExpExecArray | null
  FENCE_RE.lastIndex = 0
  while ((m = FENCE_RE.exec(md))) idxs.push(m.index)
  if (idxs.length % 2 === 0) return { head: md, tail: '', open: false }
  const cut = idxs[idxs.length - 1]
  return { head: md.slice(0, cut), tail: md.slice(cut), open: true }
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/** 渲染助手回复（streaming=true 时保护未闭合代码围栏） */
export function renderAssistantMarkdown(md: string, streaming = false): string {
  const text = (md || '').replace(/\r\n/g, '\n')
  if (!streaming) {
    return DOMPurify.sanitize(marked.parse(text) as string)
  }
  const { head, tail, open } = splitOpenFence(text)
  let html = head.trim() ? (DOMPurify.sanitize(marked.parse(head) as string)) : ''
  if (open) {
    const lang = tail.match(/^```(\w+)/)?.[1] || ''
    const codeBody = tail.replace(/^```\w*\n?/, '')
    html += `<pre class="taot-md-code-streaming"><code class="language-${lang}">${escapeHtml(codeBody)}</code></pre>`
  }
  return html
}
