<script setup>
import { computed } from 'vue'
import vehicleIcon from '../assets/vehicle-icon.png'
import { formatKm } from '../utils/format.js'

const props = defineProps({
  vehicle: { type: Object, required: true },
})

const emit = defineEmits(['select'])

const STATUS_FALLBACK = {
  label: 'Bilinmiyor',
  badge: 'bg-white/50 text-slate-600 ring-slate-400/30',
  dot: 'bg-slate-400',
}

const status = computed(() => props.vehicle.statusInfo ?? STATUS_FALLBACK)

const km = computed(() => props.vehicle.current_km ?? 0)
const formattedKm = computed(() => formatKm(km.value))

const kmBand = computed(() => {
  if (km.value < 50_000) return { fill: 'bg-emerald-400', pct: Math.min(100, (km.value / 250_000) * 100) }
  if (km.value < 150_000) return { fill: 'bg-amber-400', pct: Math.min(100, (km.value / 250_000) * 100) }
  return { fill: 'bg-rose-400', pct: Math.min(100, (km.value / 250_000) * 100) }
})
</script>

<template>
  <tr
    role="button"
    tabindex="0"
    class="group cursor-pointer border-b border-slate-100 transition-colors duration-150 last:border-0 hover:bg-slate-50/80 focus:outline-none focus:bg-slate-50"
    @click="emit('select', vehicle)"
    @keydown.enter="emit('select', vehicle)"
    @keydown.space.prevent="emit('select', vehicle)"
  >
    <td class="py-3 pl-4 pr-3">
      <div class="flex items-center gap-3">
        <div class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-900/[0.04]">
          <img :src="vehicleIcon" alt="" class="h-6 w-6 object-contain" />
        </div>
        <span class="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-sm font-black tracking-wide text-slate-900">
          {{ vehicle.plate_number }}
        </span>
      </div>
    </td>

    <td class="py-3 pr-3">
      <p class="font-bold text-slate-900">{{ vehicle.brand }} {{ vehicle.model }}</p>
      <p class="text-xs text-slate-500">{{ vehicle.production_year }} model</p>
    </td>

    <td class="py-3 pr-3">
      <span v-if="vehicle.sipp_code" class="rf-sipp-pill" :title="vehicle.segment_label || undefined">
        {{ vehicle.sipp_code }}
      </span>
    </td>

    <td class="py-3 pr-3">
      <span
        class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset"
        :class="status.badge"
      >
        <span class="h-1.5 w-1.5 rounded-full" :class="status.dot" />
        {{ status.label }}
      </span>
    </td>

    <td class="w-48 py-3 pr-4">
      <div class="flex items-center justify-between text-sm">
        <span class="font-bold text-slate-800">{{ formattedKm }}</span>
      </div>
      <div class="mt-1.5 h-1 overflow-hidden rounded-full bg-slate-900/[0.06]">
        <div class="h-full rounded-full" :class="kmBand.fill" :style="{ width: kmBand.pct + '%' }" />
      </div>
    </td>

    <td class="py-3 pr-4 text-right">
      <span class="inline-flex items-center gap-1 text-sm font-bold text-brand-600 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
        Detaylar
        <span aria-hidden="true">→</span>
      </span>
    </td>
  </tr>
</template>
