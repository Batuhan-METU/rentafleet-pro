<script setup>
// Araç ekleme / düzenleme modalı (Araçlar sayfasından).
import { onMounted, onBeforeUnmount } from 'vue'
import VehicleFinanceForm from './finance/VehicleFinanceForm.vue'

defineProps({
  editVehicle: { type: Object, default: null },
  editProfile: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved'])

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div class="absolute inset-0 bg-slate-900/50" aria-hidden="true" @click="emit('close')" />

      <div
        class="relative z-10 flex max-h-[min(90vh,100dvh-2rem)] w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
      >
        <header class="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <div class="min-w-0">
            <h2 class="text-lg font-semibold leading-tight text-slate-900">
              {{ editVehicle ? 'Araç Bilgilerini Düzenle' : 'Yeni Araç Ekle' }}
            </h2>
            <p class="mt-1 text-sm leading-snug text-slate-500">
              Maliyet ve fiyat önerileri bu bilgilere göre otomatik hesaplanır.
            </p>
          </div>
          <button
            type="button"
            class="shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Kapat"
            @click="emit('close')"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div class="flex-1 overflow-y-auto overscroll-contain px-6 py-5">
          <VehicleFinanceForm
            :edit-vehicle="editVehicle"
            :edit-profile="editProfile"
            @saved="(v) => emit('saved', v)"
            @cancel="emit('close')"
          />
        </div>
      </div>
    </div>
  </Teleport>
</template>
