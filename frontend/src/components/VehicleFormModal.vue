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
    <div class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-6" @click.self="emit('close')">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>
      <div class="relative my-4 w-full max-w-5xl overflow-hidden rounded-3xl rf-glass-strong shadow-2xl">
        <div class="rf-accent-bar" />
        <header class="sticky top-0 z-10 flex items-center justify-between border-b border-white/30 bg-white/40 px-6 py-4 backdrop-blur-md">
          <div>
            <h2 class="text-lg font-bold text-slate-900">
              {{ editVehicle ? 'Araç Bilgilerini Düzenle' : 'Yeni Araç Ekle' }}
            </h2>
            <p class="text-sm text-slate-500">
              Maliyet ve fiyat önerileri bu bilgilere göre otomatik hesaplanır.
            </p>
          </div>
          <button
            type="button"
            class="grid h-9 w-9 place-items-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
            aria-label="Kapat"
            @click="emit('close')"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>
        <div class="px-6 py-5">
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
