<script setup>
import { computed } from 'vue'

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

const kmFormatter = new Intl.NumberFormat('tr-TR')
const km = computed(() => props.vehicle.current_km ?? 0)
const formattedKm = computed(() => `${kmFormatter.format(km.value)} km`)

// SIPP ilk iki karakteri gövde sınıfını verir (bkz. seed_data.py kataloğu):
// EC/MC = ekonomik hatchback, CD = kompakt sedan, ID/SD = sedan, CF/IF = SUV, FV = ticari.
const bodyType = computed(() => {
  const code = (props.vehicle.sipp_code || '').toUpperCase()
  if (code.startsWith('CF') || code.startsWith('IF')) return 'suv'
  if (code.startsWith('FV')) return 'van'
  if (code.startsWith('ID') || code.startsWith('SD')) return 'sedan'
  return 'hatch'
})

// Kilometreye göre kabaca aşınma bandı — hızlı görsel tarama için.
const kmBand = computed(() => {
  if (km.value < 50_000) return { fill: 'bg-emerald-400', pct: Math.min(100, (km.value / 250_000) * 100) }
  if (km.value < 150_000) return { fill: 'bg-amber-400', pct: Math.min(100, (km.value / 250_000) * 100) }
  return { fill: 'bg-rose-400', pct: Math.min(100, (km.value / 250_000) * 100) }
})
</script>

<template>
  <article
    role="button"
    tabindex="0"
    class="group rf-glass rf-interactive flex cursor-pointer flex-col rounded-3xl p-5 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:ring-offset-2"
    @click="emit('select', vehicle)"
    @keydown.enter="emit('select', vehicle)"
    @keydown.space.prevent="emit('select', vehicle)"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <span class="rounded-xl border border-white/50 bg-white/40 px-3 py-1.5 text-sm font-black tracking-wide text-slate-900 backdrop-blur-sm">
          {{ vehicle.plate_number }}
        </span>
        <span v-if="vehicle.sipp_code" class="rf-sipp-pill" :title="vehicle.sinif_etiketi || undefined">
          {{ vehicle.sipp_code }}
        </span>
      </div>
      <span
        class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset backdrop-blur-sm"
        :class="status.badge"
      >
        <span class="h-1.5 w-1.5 rounded-full" :class="status.dot" />
        {{ status.label }}
      </span>
    </div>

    <div class="mt-4 flex items-start gap-3">
      <div class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-slate-900/[0.04] text-slate-500">
        <svg v-if="bodyType === 'hatch'" viewBox="0 0 32 20" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 15h1.5M27.5 15H29M5 15V11l3-5h9l5 5h4a3 3 0 013 3v1" />
          <circle cx="9" cy="15.5" r="2.5" /><circle cx="23" cy="15.5" r="2.5" />
        </svg>
        <svg v-else-if="bodyType === 'sedan'" viewBox="0 0 34 20" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M2 15h1.5M30.5 15H32M4 15V12l3-5.5h6l3 3h5l4 3h3a2 2 0 012 2v0.5" />
          <circle cx="9.5" cy="15.5" r="2.5" /><circle cx="24.5" cy="15.5" r="2.5" />
        </svg>
        <svg v-else-if="bodyType === 'suv'" viewBox="0 0 32 22" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M2 16h1.5M28.5 16H30M4 16v-5l2.5-5.5h16L27 10h1a2 2 0 012 2v4" />
          <circle cx="9.5" cy="16.5" r="2.7" /><circle cx="22.5" cy="16.5" r="2.7" />
        </svg>
        <svg v-else viewBox="0 0 34 22" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <path d="M2 16h1.5M30.5 16H32M4 16V7a2 2 0 012-2h16l6 6v5" />
          <circle cx="9.5" cy="16.5" r="2.7" /><circle cx="24.5" cy="16.5" r="2.7" />
        </svg>
      </div>
      <div class="min-w-0">
        <h3 class="truncate text-xl font-black tracking-tight text-slate-900">
          {{ vehicle.brand }} {{ vehicle.model }}
        </h3>
        <p class="mt-0.5 text-sm text-slate-500/80">{{ vehicle.production_year }} model</p>
      </div>
    </div>

    <dl class="mt-5 border-t border-white/30 pt-4 text-sm">
      <div class="flex items-center justify-between">
        <dt class="text-slate-500/80">Kilometre</dt>
        <dd class="font-bold text-slate-800">{{ formattedKm }}</dd>
      </div>
      <div class="mt-2 h-1 overflow-hidden rounded-full bg-slate-900/[0.06]">
        <div class="h-full rounded-full transition-all duration-500" :class="kmBand.fill" :style="{ width: kmBand.pct + '%' }" />
      </div>
    </dl>

    <p class="mt-4 flex items-center justify-end gap-1 text-sm font-bold text-brand-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
      Detayları gör
      <span aria-hidden="true">→</span>
    </p>
  </article>
</template>
