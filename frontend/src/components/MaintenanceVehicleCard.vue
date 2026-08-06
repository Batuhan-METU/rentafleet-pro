<script setup>
import { formatKm } from '../utils/format.js'

defineProps({
  vehicle: { type: Object, required: true },
})

function barColor(status) {
  return status === 'CRITICAL' ? 'bg-red-500' : 'bg-amber-500'
}

function dimensionClass(dimStatus) {
  if (dimStatus === 'CRITICAL') return 'text-red-600'
  if (dimStatus === 'WARNING') return 'text-amber-600'
  return 'text-slate-500'
}

function statusPill(status) {
  return status === 'CRITICAL'
    ? { label: 'ACİL', cls: 'bg-red-100 text-red-700 ring-red-600/20' }
    : { label: 'YAKLAŞIYOR', cls: 'bg-amber-100 text-amber-700 ring-amber-600/20' }
}
</script>

<template>
  <div class="rf-glass rf-interactive rounded-3xl p-5">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <div class="flex items-center gap-2">
          <span class="text-base font-bold text-slate-900">{{ vehicle.plate_number }}</span>
          <span
            class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset"
            :class="statusPill(vehicle.status).cls"
          >
            {{ statusPill(vehicle.status).label }}
          </span>
        </div>
        <p class="text-sm text-slate-500">{{ vehicle.brand_model }}</p>
      </div>
    </div>

    <!-- İlerleme çubuğu (km boyutu) -->
    <div class="mt-4">
      <div class="mb-1 flex items-center justify-between text-xs text-slate-500">
        <span>{{ formatKm(vehicle.current_km) }}</span>
        <span v-if="vehicle.target_km !== null">Hedef: {{ formatKm(vehicle.target_km) }}</span>
        <span v-else class="italic text-slate-400">KM bilinmiyor</span>
      </div>
      <div class="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          v-if="vehicle.progress_pct !== null"
          class="h-full rounded-full transition-all"
          :class="barColor(vehicle.status)"
          :style="{ width: vehicle.progress_pct + '%' }"
        ></div>
        <div
          v-else
          class="h-full w-full rounded-full bg-[repeating-linear-gradient(45deg,transparent,transparent_4px,#e2e8f0_4px,#e2e8f0_8px)]"
        ></div>
      </div>
      <div class="mt-2 flex flex-wrap items-center justify-between gap-x-4 text-sm">
        <span v-if="vehicle.remaining_km !== null" class="font-semibold" :class="dimensionClass(vehicle.km_status)">
          {{ vehicle.remaining_km <= 0 ? 'KM sınırı geçti' : `${formatKm(vehicle.remaining_km)} kaldı` }}
        </span>
        <span v-else class="text-xs text-slate-400">KM verisi girilmemiş</span>
        <span v-if="vehicle.remaining_days !== null" class="font-semibold" :class="dimensionClass(vehicle.date_status)">
          {{ vehicle.remaining_days <= 0 ? 'Süre doldu' : `${vehicle.remaining_days} gün kaldı` }}
        </span>
        <span v-else class="text-xs text-slate-400">Tarih bilgisi yok</span>
      </div>
    </div>
  </div>
</template>
