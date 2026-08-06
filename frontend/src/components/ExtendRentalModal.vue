<script setup>
// Aktif kiralama uzatma modalı — yeni dönüş tarihini seçer, sunucu aracın
// o aralıkta başka bir kiralaması olup olmadığını kontrol eder.
import { computed, ref } from 'vue'
import { useRentalStore } from '../stores/rentalStore.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { useModalLifecycle } from '../composables/useModalLifecycle.js'
import DatePicker from './vehicle-form/DatePicker.vue'
import TimePicker from './vehicle-form/TimePicker.vue'

const props = defineProps({
  rental: { type: Object, required: true },
})
const emit = defineEmits(['close', 'extended'])

const rentalStore = useRentalStore()

function pad(n) {
  return String(n).padStart(2, '0')
}

// Varsayılan: mevcut planlanan bitişten 1 gün sonrası, AYNI saatte (kullanıcının
// zaten anlaştığı teslim saatini korur).
const initial = props.rental.ended_at ? new Date(props.rental.ended_at) : new Date()
initial.setDate(initial.getDate() + 1)

const newEndedDate = ref(`${initial.getFullYear()}-${pad(initial.getMonth() + 1)}-${pad(initial.getDate())}`)
const newEndedTime = ref(`${pad(initial.getHours())}:${pad(initial.getMinutes())}`)
const submitError = ref('')
const isSubmitting = ref(false)

const newEndedAtIso = computed(() => {
  if (!newEndedDate.value || !newEndedTime.value) return null
  return new Date(`${newEndedDate.value}T${newEndedTime.value}:00`).toISOString()
})

async function confirmExtend() {
  submitError.value = ''
  isSubmitting.value = true
  try {
    await rentalStore.extendRental(props.rental.id, {
      new_ended_at: newEndedAtIso.value,
    })
    emit('extended')
    emit('close')
  } catch (err) {
    submitError.value = getApiErrorMessage(err, 'Uzatma işlemi tamamlanamadı.')
  } finally {
    isSubmitting.value = false
  }
}

useModalLifecycle(() => emit('close'))
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
            <h2 class="text-lg font-black text-slate-900">Kiralamayı Uzat</h2>
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
              Yeni Dönüş Tarihi ve Saati
            </label>
            <div class="flex gap-2">
              <DatePicker v-model="newEndedDate" />
              <TimePicker v-model="newEndedTime" />
            </div>
            <p class="mt-1 text-xs text-slate-400">
              Mevcut planlanan dönüş: {{ rental.ended_at }}
            </p>
          </div>

          <div class="rounded-2xl bg-slate-50 p-4 text-sm text-slate-600 ring-1 ring-slate-200">
            Ötelenen süre boyunca araç Aktif kalır, ceza uygulanmaz. Kiralama kapandığında
            "Geç Teslim Alınanlar" listesine düşer ve fiyat farkı (orijinal tarih ↔ ötelenen tarih)
            gösterilir. Aracın seçilen tarihte başka bir kiralaması varsa uzatma reddedilir.
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
            :disabled="isSubmitting"
            @click="confirmExtend"
          >
            {{ isSubmitting ? 'İşleniyor…' : 'Uzatmayı Onayla' }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
