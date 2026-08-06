/** SSE tabanlı AI asistanı stream istemcisi + mutasyon onayı. */
import apiClient from './api.js'
import { TOKEN_KEY } from '../utils/storageKeys.js'

const API_BASE = apiClient.defaults.baseURL

/**
 * @param {string} query
 * @param {Array<{role: 'user'|'ai', text: string}>} history Önceki turlar (en fazla ~12 tanesi gönderilir).
 * @param {{
 *   onChunk: (text: string) => void,
 *   onConfirmation?: (confirmation: {action_id: string, tool: string, summary: string}) => void,
 *   onDone?: () => void,
 *   onError?: (msg: string) => void,
 * }} handlers
 */
export async function streamAiConsult(query, history, { onChunk, onConfirmation, onDone, onError }) {
  const token = localStorage.getItem(TOKEN_KEY)
  const response = await fetch(`${API_BASE}ai/consult/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    body: JSON.stringify({ query, history }),
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
      if (payload.confirmation) {
        onConfirmation?.(payload.confirmation)
      }
      if (payload.content) {
        onChunk(payload.content)
      }
    }
  }

  onDone?.()
}

/**
 * Bir AI onay kartındaki mutasyon eylemini gerçekten çalıştırır.
 * @param {string} actionId
 * @returns {Promise<object>} Eylemin sonucu (ör. oluşturulan kiralama).
 */
export async function confirmAiAction(actionId) {
  const response = await apiClient.post(`ai/actions/${actionId}/confirm/`)
  return response.data
}
