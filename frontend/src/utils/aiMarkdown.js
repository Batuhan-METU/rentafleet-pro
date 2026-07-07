/** AI yanıtları için hafif Markdown → HTML (ChatGPT tarzı). */

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * **kalın**, madde listeleri ve paragrafları HTML'e çevirir.
 * @param {string} source
 * @returns {string}
 */
export function formatAiMarkdown(source) {
  if (!source) return ''

  let text = escapeHtml(source)
  // Tamamlanmış **kalın** ifadeler
  text = text.replace(/\*\*([^*\n]+)\*\*/g, '<strong class="ai-strong">$1</strong>')

  const lines = text.split('\n')
  const parts = []
  let inList = false

  const closeList = () => {
    if (inList) {
      parts.push('</ul>')
      inList = false
    }
  }

  for (const line of lines) {
    const trimmed = line.trim()
    const bullet = trimmed.match(/^[-*•]\s+(.+)/)
    const numbered = trimmed.match(/^\d+\.\s+(.+)/)

    if (bullet || numbered) {
      if (!inList) {
        parts.push('<ul class="ai-list">')
        inList = true
      }
      const content = bullet ? bullet[1] : numbered[1]
      parts.push(
        `<li class="ai-list-item"><span class="ai-bullet" aria-hidden="true">•</span><span class="ai-list-text">${content}</span></li>`,
      )
      continue
    }

    closeList()

    if (!trimmed) {
      parts.push('<div class="ai-spacer"></div>')
      continue
    }

    parts.push(`<p class="ai-paragraph">${line}</p>`)
  }

  closeList()
  return parts.join('')
}
