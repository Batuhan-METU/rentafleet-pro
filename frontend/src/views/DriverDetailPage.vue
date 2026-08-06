<script setup>
import DriverDetailOverview from '../components/driver-detail/DriverDetailOverview.vue'
import DriverDetailRisk from '../components/driver-detail/DriverDetailRisk.vue'
import DriverDetailEligibleVehicles from '../components/driver-detail/DriverDetailEligibleVehicles.vue'
import DriverDetailRentalHistory from '../components/driver-detail/DriverDetailRentalHistory.vue'

defineProps({
  driver: { type: Object, default: null },
  rentalHistory: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'go-rental', 'rented'])
</script>

<template>
  <div v-if="driver">
    <button
      type="button"
      class="mb-5 flex items-center gap-2 text-sm font-bold text-slate-600 hover:text-slate-900"
      @click="emit('close')"
    >
      <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
      <span class="underline underline-offset-2">Tüm Sürücülere Dön</span>
    </button>

    <!-- Sekmeli sağ/sol panel yerine tüm kısımlar alt alta tek sayfada -->
    <div class="space-y-6">
      <DriverDetailOverview :driver="driver" @go-rental="emit('go-rental')" @rented="emit('rented')" />
      <DriverDetailRisk :driver="driver" />
      <DriverDetailEligibleVehicles :driver="driver" />

      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <h3 class="mb-3 text-sm font-bold uppercase tracking-wider text-slate-500">Kiralama Geçmişi</h3>
        <DriverDetailRentalHistory :rentals="rentalHistory" />
      </section>
    </div>
  </div>

  <div v-else class="grid h-full place-items-center">
    <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
  </div>
</template>
