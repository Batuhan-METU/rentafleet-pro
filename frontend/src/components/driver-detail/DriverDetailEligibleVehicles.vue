<script setup>
import { computed, onMounted, ref } from 'vue'
import { useVehicleStore } from '../../stores/vehicleStore.js'

const props = defineProps({
  driver: { type: Object, required: true },
})

const vehicleStore = useVehicleStore()
const showAllVehicles = ref(false)

const risk = computed(() => props.driver?.risk ?? null)
const filteredVehicles = computed(() => risk.value?.uygun_araclar ?? [])

// Filtre kaldırıldığında kartların yerleri değişmesin diye: önce uygun
// araçlar (zaten göründükleri sırayla), ardından sadece filtre kalkınca
// eklenen ekstra araçlar sona eklenir — baştan sona yeniden sıralanmaz.
const allFleetVehicles = computed(() => {
  const filteredIds = new Set(filteredVehicles.value.map((v) => v.vehicle_id))
  const extra = vehicleStore.vehicles
    .filter((v) => v.status === 'AVAILABLE' && !filteredIds.has(v.id))
    .map((v) => ({
      vehicle_id: v.id,
      plate_number: v.plate_number,
      brand: v.brand,
      model: v.model,
      segment_label: v.segment_label || '—',
      sipp_code: v.sipp_code,
    }))
  return [...filteredVehicles.value, ...extra]
})

const vehicles = computed(() =>
  showAllVehicles.value ? allFleetVehicles.value : filteredVehicles.value,
)

onMounted(() => {
  if (!vehicleStore.vehicles.length) void vehicleStore.fetchVehicles()
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h3 class="text-sm font-bold uppercase tracking-wider text-slate-500">
        {{ showAllVehicles ? 'Tüm Araçlar' : 'Uygun Araçlar' }}
      </h3>
      <button
        type="button"
        class="rounded-full px-3 py-1 text-xs font-bold transition"
        :class="showAllVehicles
          ? 'bg-brand-600 text-white'
          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
        @click="showAllVehicles = !showAllVehicles"
      >
        {{ showAllVehicles ? 'Filtreyi Uygula' : 'Filtreyi Kaldır' }}
      </button>
    </div>
    <div v-if="vehicles.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <div
        v-for="vehicle in vehicles"
        :key="vehicle.vehicle_id"
        class="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3"
      >
        <p class="font-black text-slate-900">{{ vehicle.plate_number }}</p>
        <p class="text-sm text-slate-600">{{ vehicle.brand }} {{ vehicle.model }}</p>
        <p class="mt-1 text-xs font-semibold text-brand-600">{{ vehicle.segment_label }} · {{ vehicle.sipp_code }}</p>
      </div>
    </div>
    <p v-else class="text-sm text-slate-500">
      {{ showAllVehicles
        ? 'Müsait araç bulunamadı.'
        : (risk?.blokajlar?.length ? 'Risk nedeniyle uygun araç bulunamadı.' : 'Uygun araç listesi boş.') }}
    </p>
  </section>
</template>
