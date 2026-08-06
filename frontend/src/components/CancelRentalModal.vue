<script setup>
// Kiralama iptali onay modalı — native window.confirm() yerine özel overlay.
import { ref } from 'vue'
import { useRentalStore } from '../stores/rentalStore.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { useModalLifecycle } from '../composables/useModalLifecycle.js'
import { formatDate } from '../utils/format.js'

const props = defineProps({
  rental: { type: Object, required: true },
})
const emit = defineEmits(['close', 'cancelled'])

const rentalStore = useRentalStore()
const submitError = ref('')
const isSubmitting = ref(false)

async function confirmCancel() {
  submitError.value = ''
  isSubmitting.value = true
  try {
    await rentalStore.cancelRental(props.rental.id)
    emit('cancelled')
    emit('close')
  } catch (err) {
    submitError.value = getApiErrorMessage(err, 'Kiralama iptal edilemedi.')
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
            <h2 class="text-lg font-black text-slate-900">Kiralamayı İptal Et</h2>
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
          <dl class="grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-4 text-sm ring-1 ring-slate-200">
            <div>
              <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Sürücü</dt>
              <dd class="mt-0.5 font-semibold text-slate-800">{{ rental.driver_name }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Araç</dt>
              <dd class="mt-0.5 font-semibold text-slate-800">{{ rental.plate_number }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Alış</dt>
              <dd class="mt-0.5 text-slate-700">{{ formatDate(rental.started_at) }}</dd>
            </div>
            <div>
              <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Bırakış</dt>
              <dd class="mt-0.5 text-slate-700">{{ formatDate(rental.ended_at) }}</dd>
            </div>
          </dl>

          <p class="text-sm text-slate-600">
            {{ rental.driver_name }} için bu kiralamayı iptal etmek istediğinize emin misiniz?
            <span v-if="rental.period_code === 'UPCOMING'">Henüz başlamadığı için ek bir ücret farkı oluşmaz.</span>
            <span v-else>Şu ana kadarki kullanım üzerinden erken teslim olarak işlenir ve fiyat farkı hesaplanır.</span>
          </p>

          <p v-if="submitError" class="text-sm font-semibold text-rose-600">{{ submitError }}</p>
        </div>

        <footer class="flex items-center justify-end gap-3 border-t border-slate-100 px-6 py-4">
          <button type="button" class="rf-pill-filter rf-pill-filter--idle" @click="emit('close')">
            Vazgeç
          </button>
          <button
            type="button"
            class="rounded-lg border border-rose-600 bg-rose-600 px-4 py-2 text-sm font-bold text-white transition-colors hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="isSubmitting"
            @click="confirmCancel"
          >
            {{ isSubmitting ? 'İşleniyor…' : 'Evet, İptal Et' }}
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
