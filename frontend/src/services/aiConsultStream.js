/** SSE tabanlı AI danışman stream istemcisi. */
import apiClient from './api.js'

const API_BASE = apiClient.defaults.baseURL

/**
 * @param {string} query
 * @param {{ onChunk: (text: string) => void, onDone?: () => void, onError?: (msg: string) => void }} handlers
 */
export async function streamAiConsult(query, { onChunk, onDone, onError }) {
  const token = localStorage.getItem('rf_token')
  const response = await fetch(`${API_BASE}ai/consult/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    body: JSON.stringify({ query }),
  })

  if (!response.ok) {
    const errText = await response.text().catch(() => '')
    let message = errText || `HTTP ${response.status}`
    try {
      const parsed = JSON.parse(errText)
      message = parsed.detail || parsed.error || message
    } catch {
      // düz metin veya HTML hata gövdesi
    }
    throw new Error(message)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('Tarayıcı stream desteklemiyor.')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue

      const raw = trimmed.slice(5).trim()
      if (!raw) continue

      let payload
      try {
        payload = JSON.parse(raw)
      } catch {
        continue
      }

      if (payload.error) {
        onError?.(payload.error)
        return
      }
      if (payload.done) {
        onDone?.()
        return
      }
      if (payload.content) {
        onChunk(payload.content)
      }
    }
  }

  onDone?.()
}
