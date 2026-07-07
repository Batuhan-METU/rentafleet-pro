<script setup>
import { ref, nextTick, watch, onBeforeUnmount, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { streamAiConsult } from '../services/aiConsultStream.js'
import { formatAiMarkdown } from '../utils/aiMarkdown.js'
import { useUiStore } from '../stores/uiStore.js'
import { useBrandingStore } from '../stores/brandingStore.js'

const TYPEWRITER_MS = 22

const ui = useUiStore()
const branding = useBrandingStore()
const { aiChatOpen: isOpen } = storeToRefs(ui)

const input = ref('')
const loading = ref(false)
const messages = ref([
  {
    role: 'ai',
    text: 'Merhaba! Ben **RentA-Fleet PRO** yapay zeka filo danışmanınızım. Filonuzla ilgili şu konularda soru sorabilirsiniz:\n\n- Risk ve güvenlik\n- Bakım planlaması\n- Fiyatlandırma stratejisi\n- Doluluk analizi',
    fullText: 'Merhaba! Ben **RentA-Fleet PRO** yapay zeka filo danışmanınızım. Filonuzla ilgili şu konularda soru sorabilirsiniz:\n\n- Risk ve güvenlik\n- Bakım planlaması\n- Fiyatlandırma stratejisi\n- Doluluk analizi',
    streaming: false,
  },
])

const suggestions = [
  'Hangi araçlar riskte?',
  'Bakım önerisi ver',
  'Fiyatlandırma stratejisi nasıl olmalı?',
]

const scrollAnchor = ref(null)
const messagesContainer = ref(null)
const activeTypewriters = new Set()

const headerGradient = computed(() =>
  `linear-gradient(135deg, ${branding.secondary_color}, ${branding.primary_color})`,
)

async function scrollToBottom(smooth = true) {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTo({
      top: messagesContainer.value.scrollHeight,
      behavior: smooth ? 'smooth' : 'auto',
    })
  } else {
    scrollAnchor.value?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'end' })
  }
}

watch(messages, () => scrollToBottom(true), { deep: true })
watch(isOpen, (open) => {
  if (open) scrollToBottom(false)
})

function renderAiHtml(msg) {
  return formatAiMarkdown(msg.text)
}

function isTyping(msg) {
  return msg.streaming || (msg.fullText && msg.text.length < msg.fullText.length)
}

function startTypewriter(index) {
  if (activeTypewriters.has(index)) return
  activeTypewriters.add(index)

  const tick = () => {
    const msg = messages.value[index]
    if (!msg) {
      activeTypewriters.delete(index)
      return
    }

    const target = msg.fullText ?? msg.text ?? ''
    if (msg.text.length < target.length) {
      msg.text += target[msg.text.length]
      setTimeout(tick, TYPEWRITER_MS)
      return
    }

    if (msg.streaming) {
      setTimeout(tick, TYPEWRITER_MS)
      return
    }

    activeTypewriters.delete(index)
  }

  tick()
}

function toggle() {
  ui.toggleAiChat()
}

async function send(text) {
  const query = (text ?? input.value).trim()
  if (!query || loading.value) return

  messages.value.push({ role: 'user', text: query, streaming: false })
  input.value = ''
  loading.value = true

  const aiIndex = messages.value.length
  messages.value.push({ role: 'ai', text: '', fullText: '', streaming: true })

  try {
    await streamAiConsult(query, {
      onChunk: (chunk) => {
        if (loading.value) loading.value = false
        messages.value[aiIndex].fullText += chunk
        startTypewriter(aiIndex)
      },
      onDone: () => {
        loading.value = false
        if (messages.value[aiIndex]) {
          messages.value[aiIndex].streaming = false
          startTypewriter(aiIndex)
        }
      },
      onError: (msg) => {
        loading.value = false
        const errText = `Üzgünüm, bir hata oluştu: ${msg}`
        messages.value[aiIndex] = {
          role: 'ai',
          text: errText,
          fullText: errText,
          streaming: false,
        }
      },
    })
  } catch (err) {
    loading.value = false
    const detail = err instanceof Error ? err.message : 'Bilinmeyen hata'
    const errText = `Üzgünüm, analiz servisine ulaşılamadı: ${detail}`
    messages.value[aiIndex] = {
      role: 'ai',
      text: errText,
      fullText: errText,
      streaming: false,
    }
  } finally {
    if (messages.value[aiIndex]) {
      messages.value[aiIndex].streaming = false
      startTypewriter(aiIndex)
    }
    loading.value = false
    scrollToBottom()
  }
}

onBeforeUnmount(() => {
  activeTypewriters.clear()
})
</script>

<template>
  <div class="fixed bottom-6 right-6 z-50 flex flex-col items-end">
    <transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="translate-y-6 scale-95 opacity-0"
      enter-to-class="translate-y-0 scale-100 opacity-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="translate-y-0 scale-100 opacity-100"
      leave-to-class="translate-y-6 scale-95 opacity-0"
    >
      <div
        v-if="isOpen"
        class="rf-glass-strong mb-4 flex h-[36rem] w-[26rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-3xl shadow-2xl"
      >
        <div class="rf-accent-bar" />
        <header
          class="flex shrink-0 items-center gap-3 px-5 py-4 text-white"
          :style="{ background: headerGradient }"
        >
          <div class="grid h-11 w-11 place-items-center rounded-2xl bg-white/20 text-xl backdrop-blur-sm">✨</div>
          <div class="min-w-0">
            <p class="truncate text-sm font-black">AI Filo Danışmanı</p>
            <p class="flex items-center gap-1.5 text-xs text-white/75">
              <span
                class="h-2 w-2 rounded-full"
                :class="loading ? 'animate-pulse bg-amber-300' : 'bg-emerald-300'"
              />
              {{ loading ? 'Yanıt yazılıyor…' : 'Çevrimiçi' }}
            </p>
          </div>
          <button
            type="button"
            class="ml-auto grid h-9 w-9 place-items-center rounded-xl text-white/80 transition-all duration-300 hover:bg-white/20 hover:text-white"
            aria-label="Kapat"
            @click="toggle"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div
          ref="messagesContainer"
          class="chat-scroll flex-1 space-y-4 overflow-y-auto px-4 py-5 scroll-smooth"
          style="background: rgba(255,255,255,0.15); backdrop-filter: blur(16px);"
        >
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="flex animate-fade-in gap-2.5"
            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              v-if="msg.role === 'ai'"
              class="grid h-8 w-8 shrink-0 place-items-center self-end rounded-xl text-sm"
              :style="{ background: `color-mix(in srgb, ${branding.primary_color} 18%, white)` }"
            >
              🤖
            </div>

            <div
              class="max-w-[82%] px-4 py-3 text-sm shadow-sm transition-all duration-300"
              :class="[
                msg.role === 'user'
                  ? 'rounded-3xl rounded-br-md text-white'
                  : 'rf-glass rounded-3xl rounded-bl-md text-slate-700 ai-message',
                msg.streaming && !msg.text ? 'opacity-80' : 'opacity-100',
              ]"
              :style="msg.role === 'user' ? { background: `linear-gradient(135deg, ${branding.primary_color}, color-mix(in srgb, ${branding.primary_color} 80%, ${branding.secondary_color}))` } : undefined"
            >
              <div
                v-if="msg.role === 'ai' && msg.text"
                class="ai-prose"
                v-html="renderAiHtml(msg)"
              />
              <span v-else-if="msg.role === 'user'" class="font-medium">{{ msg.text }}</span>
              <span
                v-else-if="msg.streaming"
                class="inline-flex items-center gap-1.5 text-slate-400"
              >
                <span class="h-1.5 w-1.5 animate-pulse rounded-full" :style="{ backgroundColor: branding.primary_color }" />
                Düşünüyor…
              </span>
              <span
                v-if="msg.role === 'ai' && isTyping(msg)"
                class="ai-cursor"
                aria-hidden="true"
              />
            </div>
          </div>

          <div v-if="messages.length === 1 && !loading" class="flex flex-wrap gap-2 pl-10 pt-1">
            <button
              v-for="s in suggestions"
              :key="s"
              type="button"
              class="rf-glass rounded-full px-3.5 py-2 text-xs font-semibold text-slate-700 transition-all duration-300 ease-in-out hover:-translate-y-0.5 hover:shadow-md"
              @click="send(s)"
            >
              {{ s }}
            </button>
          </div>

          <div ref="scrollAnchor" />
        </div>

        <form class="flex items-center gap-2 border-t border-white/30 bg-white/40 px-4 py-3 backdrop-blur-md" @submit.prevent="send()">
          <input
            v-model="input"
            type="text"
            placeholder="Bir soru yazın..."
            :disabled="loading"
            class="rf-input flex-1 !rounded-2xl"
          />
          <button
            type="submit"
            :disabled="loading || !input.trim()"
            class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-white transition-all duration-300 ease-in-out hover:scale-105 disabled:cursor-not-allowed disabled:opacity-50"
            :style="{ background: `linear-gradient(135deg, ${branding.primary_color}, ${branding.secondary_color})` }"
            aria-label="Gönder"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </form>
      </div>
    </transition>

    <button
      type="button"
      class="group relative grid h-16 w-16 place-items-center rounded-full text-white shadow-2xl transition-all duration-300 ease-in-out hover:scale-110"
      :style="{
        background: `linear-gradient(135deg, ${branding.primary_color}, ${branding.secondary_color})`,
        boxShadow: `0 8px 32px color-mix(in srgb, ${branding.primary_color} 45%, transparent)`,
      }"
      :aria-label="isOpen ? 'Danışmanı kapat' : 'AI Danışmanı aç'"
      @click="toggle"
    >
      <span v-if="!isOpen" class="absolute -right-0.5 -top-0.5 flex h-4 w-4">
        <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
        <span class="relative inline-flex h-4 w-4 rounded-full bg-emerald-500" />
      </span>
      <svg v-if="isOpen" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
      <svg v-else class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4-.8L3 20l1.3-3.2A7.96 7.96 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.chat-scroll {
  scroll-behavior: smooth;
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in {
  animation: fade-in 0.3s ease-out;
}

.ai-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--primary-color);
  animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
  50% {
    opacity: 0;
  }
}

:deep(.ai-prose) {
  line-height: 1.65;
  font-size: 0.875rem;
}

:deep(.ai-paragraph) {
  margin: 0 0 0.5rem;
}

:deep(.ai-paragraph:last-child) {
  margin-bottom: 0;
}

:deep(.ai-strong) {
  font-weight: 700;
  color: #0f172a;
}

:deep(.ai-list) {
  margin: 0.35rem 0 0.65rem;
  padding: 0;
  list-style: none;
}

:deep(.ai-list-item) {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}

:deep(.ai-list-item:last-child) {
  margin-bottom: 0;
}

:deep(.ai-bullet) {
  flex-shrink: 0;
  width: 1rem;
  color: #64748b;
  font-weight: 700;
  line-height: 1.65;
  text-align: center;
}

:deep(.ai-list-text) {
  flex: 1;
  min-width: 0;
}

:deep(.ai-spacer) {
  height: 0.35rem;
}
</style>
