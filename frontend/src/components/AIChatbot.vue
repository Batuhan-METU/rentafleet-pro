<script setup>
// AI Filo Danışmanı — sağ alt köşede açılır/kapanır sohbet widget'ı.
// Kullanıcı Türkçe soru yazar, "Yapay Zeka düşünüyor..." durumu gösterilir ve
// yanıtlar sohbet balonları halinde eklenir. Sohbet durumu bileşene özeldir;
// backend'e POST /ai/consult/ ile bağlanır.
import { ref, nextTick, watch } from 'vue'
import apiClient from '../services/api.js'

const isOpen = ref(false)
const input = ref('')
const loading = ref(false)
const messages = ref([
  {
    role: 'ai',
    text: 'Merhaba! Ben RentA-Fleet PRO yapay zeka filo danışmanınızım. Filonuzla ilgili risk, bakım, fiyatlandırma veya doluluk hakkında soru sorabilirsiniz.',
  },
])

const suggestions = [
  'Hangi araçlar riskte?',
  'Bakım önerisi ver',
  'Fiyatlandırma stratejisi nasıl olmalı?',
]

const scrollAnchor = ref(null)

async function scrollToBottom() {
  await nextTick()
  scrollAnchor.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
}

watch(messages, scrollToBottom, { deep: true })
watch(isOpen, (open) => {
  if (open) scrollToBottom()
})

function toggle() {
  isOpen.value = !isOpen.value
}

async function send(text) {
  const query = (text ?? input.value).trim()
  if (!query || loading.value) return

  messages.value.push({ role: 'user', text: query })
  input.value = ''
  loading.value = true

  try {
    const { data } = await apiClient.post('ai/consult/', { query })
    messages.value.push({ role: 'ai', text: data.response })
  } catch {
    messages.value.push({
      role: 'ai',
      text: 'Üzgünüm, şu anda analiz servisine ulaşılamıyor. Lütfen biraz sonra tekrar deneyin.',
    })
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="fixed bottom-6 right-6 z-50 flex flex-col items-end">
    <!-- Sohbet penceresi -->
    <transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="translate-y-4 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-4 opacity-0"
    >
      <div
        v-if="isOpen"
        class="mb-3 flex h-[32rem] w-[22rem] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
      >
        <!-- Başlık -->
        <header class="flex items-center gap-3 bg-gradient-to-r from-brand-700 to-brand-500 px-4 py-3 text-white">
          <div class="grid h-9 w-9 place-items-center rounded-full bg-white/20 text-lg">🤖</div>
          <div class="min-w-0">
            <p class="truncate text-sm font-bold">AI Filo Danışmanı</p>
            <p class="flex items-center gap-1.5 text-xs text-white/80">
              <span class="h-2 w-2 rounded-full bg-emerald-300"></span> Çevrimiçi
            </p>
          </div>
          <button
            type="button"
            class="ml-auto grid h-8 w-8 place-items-center rounded-lg text-white/80 transition hover:bg-white/20 hover:text-white"
            aria-label="Kapat"
            @click="toggle"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <!-- Mesajlar -->
        <div class="flex-1 space-y-3 overflow-y-auto bg-slate-50 px-4 py-4">
          <div
            v-for="(msg, i) in messages"
            :key="i"
            class="flex"
            :class="msg.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              class="max-w-[85%] whitespace-pre-line rounded-2xl px-3.5 py-2.5 text-sm shadow-sm"
              :class="msg.role === 'user'
                ? 'rounded-br-sm bg-brand-600 text-white'
                : 'rounded-bl-sm border border-slate-200 bg-white text-slate-700'"
            >
              {{ msg.text }}
            </div>
          </div>

          <!-- Düşünüyor -->
          <div v-if="loading" class="flex justify-start">
            <div class="flex items-center gap-2 rounded-2xl rounded-bl-sm border border-slate-200 bg-white px-3.5 py-2.5 text-sm text-slate-500 shadow-sm">
              <span class="flex gap-1">
                <span class="h-2 w-2 animate-bounce rounded-full bg-brand-400 [animation-delay:-0.3s]"></span>
                <span class="h-2 w-2 animate-bounce rounded-full bg-brand-400 [animation-delay:-0.15s]"></span>
                <span class="h-2 w-2 animate-bounce rounded-full bg-brand-400"></span>
              </span>
              Yapay Zeka düşünüyor...
            </div>
          </div>

          <!-- Hızlı öneriler (yalnızca ilk karşılamada) -->
          <div v-if="messages.length === 1 && !loading" class="flex flex-wrap gap-2 pt-1">
            <button
              v-for="s in suggestions"
              :key="s"
              type="button"
              class="rounded-full border border-brand-200 bg-white px-3 py-1.5 text-xs font-medium text-brand-700 transition hover:bg-brand-50"
              @click="send(s)"
            >
              {{ s }}
            </button>
          </div>

          <div ref="scrollAnchor"></div>
        </div>

        <!-- Girdi -->
        <form class="flex items-center gap-2 border-t border-slate-200 bg-white px-3 py-3" @submit.prevent="send()">
          <input
            v-model="input"
            type="text"
            placeholder="Bir soru yazın..."
            :disabled="loading"
            class="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-700 outline-none transition focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-100 disabled:opacity-60"
          />
          <button
            type="submit"
            :disabled="loading || !input.trim()"
            class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-brand-600 text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Gönder"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </button>
        </form>
      </div>
    </transition>

    <!-- Açma/kapama düğmesi -->
    <button
      type="button"
      class="group relative grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-brand-600 to-brand-500 text-white shadow-lg shadow-brand-600/30 transition hover:scale-105 hover:shadow-xl"
      :aria-label="isOpen ? 'Danışmanı kapat' : 'AI Danışmanı aç'"
      @click="toggle"
    >
      <span v-if="!isOpen" class="absolute -right-0.5 -top-0.5 flex h-3.5 w-3.5">
        <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
        <span class="relative inline-flex h-3.5 w-3.5 rounded-full bg-emerald-500"></span>
      </span>
      <svg v-if="isOpen" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
      <svg v-else class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4-.8L3 20l1.3-3.2A7.96 7.96 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    </button>
  </div>
</template>
