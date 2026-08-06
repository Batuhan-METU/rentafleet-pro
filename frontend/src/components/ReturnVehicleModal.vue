<script setup>
// Araç teslim alma modalı — erken/geç/zamanında farkını canlı önizler,
// onaylanınca kiralamayı kapatıp aracı serbest bırakır.
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRentalStore } from '../stores/rentalStore.js'
import { formatTL } from '../utils/format.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { useModalLifecycle } from '../composables/useModalLifecycle.js'
import DatePicker from './vehicle-form/DatePicker.vue'
import TimePicker from './vehicle-form/TimePicker.vue'

const props = defineProps({
  rental: { type: Object, required: true },
})
const emit = defineEmits(['close', 'returned'])

const rentalStore = useRentalStore()

function pad(n) {
  return String(n).padStart(2, '0')
}

const now = new Date()
const actualReturnDate = ref(`${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`)
const actualReturnTime = ref(`${pad(now.getHours())}:${pad(now.getMinutes())}`)
const notes = ref('')
const preview = ref(null)
const previewError = ref('')
const submitError = ref('')

const actualReturnAtIso = computed(() => {
  if (!actualReturnDate.value || !actualReturnTime.value) return null
  return new Date(`${actualReturnDate.value}T${actualReturnTime.value}:00`).toISOString()
})

let debounceTimer = null

async function refreshPreview() {
  if (!actualReturnAtIso.value) return
  previewError.value = ''
  try {
    preview.value = await rentalStore.previewReturn(props.rental.id, {
      actual_return_at: actualReturnAtIso.value,
      notes: notes.value,
    })
  } catch (err) {
    preview.value = null
    previewError.value = getApiErrorMessage(err, 'Önizleme hesaplanamadı.')
  }
}

watch([actualReturnDate, actualReturnTime, notes], () => {
  clearTimeout(debounceTimer)
  debounceTimer = window.setTimeout(refreshPreview, 400)
})

const previewTone = computed(() => {
  if (!preview.value) return 'neutral'
  if (preview.value.status === 'EARLY') return 'refund'
  if (preview.value.status === 'LATE') return 'charge'
  return 'neutral'
})

const submitting = computed(() => rentalStore.returningId === props.rental.id)

async function confirmReturn() {
  submitError.value = ''
  try {
    await rentalStore.returnRental(props.rental.id, {
      actual_return_at: actualReturnAtIso.value,
      notes: notes.value,
    })
    emit('returned')
    emit('close')
  } catch (err) {
    submitError.value = getApiErrorMessage(err, 'Teslim alma işlemi tamamlanamadı.')
  }
}

useModalLifecycle(() => emit('close'))

onMounted(() => {
  refreshPreview()
})

onBeforeUnmount(() => {
  clearTimeout(debounceTimer)
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div class="absolute inset-0 bg-slate-900/50" aria-hidden="true" @click="emit('close')" />

      <div
        class="relative z-10 w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
      >
        <div class="rf-accent-bar" />

        <header class="flex items-start justify-between gap-4 px-6 pt-5">
          <div>
            <h2 class="text-lg font-black text-slate-900">Araç Teslim Al</h2>
            <p class="mt-0.5 text-sm text-slate-500">{{ rental.plate_number }} — {{ rental.brand_model }}</p>
          </div>
          <button
            type="button"
            class="cursor-pointer rounded-full p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            @click="emit('close')"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div class="space-y-4 px-6 py-5">
          <div>
            <label class="mb-1 block text-xs font-bold uppercase tracking-wide text-slate-500">
              Fiili Teslim Zamanı
            </label>
            <div class="flex gap-2">
              <DatePicker v-model="actualReturnDate" />
              <TimePicker v-model="actualReturnTime" />
            </div>
            <p class="mt-1 text-xs text-slate-400">Sözleşme dönüş tarihi: {{ rental.ended_at }}</p>
          </div>

          <div>
            <label class="mb-1 block text-xs font-bold uppercase tracking-wide text-slate-500">Not (opsiyonel)</label>
            <textarea v-model="notes" rows="2" class="rf-input resize-none" placeholder="Hasar, yakıt durumu vb." />
          </div>

          <div
            class="rounded-2xl p-4 ring-1 transition-colors"
            :class="{
              'bg-emerald-50 ring-emerald-200': previewTone === 'refund',
              'bg-rose-50 ring-rose-200': previewTone === 'charge',
              'bg-slate-50 ring-slate-200': previewTone === 'neutral',
            }"
          >
            <template v-if="previewError">
              <p class="text-sm font-semibold text-rose-700">{{ previewError }}</p>
            </template>
            <template v-else-if="preview">
              <p class="text-sm font-bold text-slate-800">{{ preview.message }}</p>
              <p v-if="Number(preview.price_difference) !== 0" class="mt-1 font-display text-2xl font-black tabular-nums" :class="previewTone === 'refund' ? 'text-emerald-700' : 'text-rose-700'">
                {{ previewTone === 'refund' ? '−' : '+' }}{{ formatTL(Math.abs(Number(preview.price_difference))) }}
              </p>
            </template>
            <template v-else>
              <p class="text-sm text-slate-500">Hesaplanıyor…</p>
            </template>
          </div>

          <p v-if="submitError" class="text-sm font-semibold text-rose-600">{{ submitError }}</p>
        </div>

        <footer class="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-4">
          <button type="button" class="rf-pill-filter rf-pill-filter--idle" @click="emit('close')">
            Vazgeç
          </button>
          <button
            type="button"
            class="rf-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="submitting || !preview"
            @click="confirmReturn"
          >
            {{ submitting ? 'İşleniyor…' : 'Farkı Onayla ve İade/Tahsilat Yap' }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
