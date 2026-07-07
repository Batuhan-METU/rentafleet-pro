<script setup>
import { computed, onMounted } from 'vue'
import { useVehicleStore } from '../stores/vehicleStore.js'

const store = useVehicleStore()

onMounted(() => store.fetchFleetAnalytics())

const a = computed(() => store.fleetAnalytics)
const totalVehicles = computed(() => a.value?.toplam_arac ?? store.statusCounts.total)

const occupancy = computed(() => {
  if (a.value) return a.value.doluluk_orani
  const { total, RENTED } = store.statusCounts
  return total ? Math.round((RENTED / total) * 1000) / 10 : 0
})

const criticalCount = computed(() => a.value?.aktif_kritik_anomali ?? null)
const avgScore = computed(() => a.value?.ortalama_surus_skoru ?? null)

const scoreAccent = computed(() => {
  const s = avgScore.value
  if (s == null) return 'text-slate-900'
  if (s >= 80) return 'text-emerald-600'
  if (s >= 70) return 'text-amber-600'
  return 'text-red-600'
})

const loading = computed(() => store.analyticsLoading && !a.value)
</script>

<template>
  <div class="grid grid-cols-12 gap-4">
    <!-- Hero: doluluk oranı (büyük asimetrik kart) -->
    <div class="rf-glass rf-interactive col-span-12 flex flex-col justify-between rounded-3xl p-6 lg:col-span-5 lg:row-span-2 lg:min-h-[220px]">
      <div class="flex items-start justify-between">
        <div>
          <p class="text-xs font-bold uppercase tracking-widest text-slate-500/80">Anlık Doluluk</p>
          <p class="mt-3 text-5xl font-black tracking-tight text-brand-600">%{{ occupancy }}</p>
        </div>
        <span class="rf-icon-ring shrink-0 !h-12 !w-12">
          <svg class="h-6 w-6 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        </span>
      </div>
      <div class="mt-6">
        <div class="h-2.5 w-full overflow-hidden rounded-full bg-white/40">
          <div
            class="h-full rounded-full transition-all duration-500 ease-out"
            :style="{
              width: Math.min(100, occupancy) + '%',
              background: 'linear-gradient(90deg, var(--primary-color), color-mix(in srgb, var(--secondary-color) 60%, var(--primary-color)))',
            }"
          />
        </div>
        <p class="mt-2 text-xs text-slate-500/80">Kirada olan araçların filo içindeki payı</p>
      </div>
    </div>

    <!-- Kompakt kapsüller -->
    <div class="rf-capsule col-span-6 flex items-center gap-4 lg:col-span-3">
      <span class="rf-icon-ring shrink-0 !h-10 !w-10">
        <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1" />
        </svg>
      </span>
      <div>
        <p class="text-[11px] font-bold uppercase tracking-wider text-slate-500/75">Toplam Araç</p>
        <p class="text-2xl font-black text-slate-900">{{ totalVehicles }}</p>
      </div>
    </div>

    <div class="rf-capsule col-span-6 flex items-center gap-4 lg:col-span-4">
      <span class="rf-icon-ring shrink-0 !h-10 !w-10">
        <svg class="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
          <path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.196-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118L2.07 9.801c-.783-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
        </svg>
      </span>
      <div>
        <p class="text-[11px] font-bold uppercase tracking-wider text-slate-500/75">Sürüş Skoru</p>
        <p v-if="loading" class="text-2xl font-black text-slate-300">—</p>
        <p v-else class="text-2xl font-black" :class="scoreAccent">
          {{ avgScore ?? '—' }}<span class="text-sm font-semibold text-slate-400">/100</span>
        </p>
      </div>
    </div>

    <!-- Kritik anomaliler (geniş uyarı kartı) -->
    <div
      class="rf-glass rf-interactive col-span-12 rounded-3xl p-5 lg:col-span-7"
      :class="criticalCount ? 'ring-1 ring-red-300/50' : ''"
    >
      <div class="flex items-center justify-between gap-4">
        <div>
          <p class="text-[11px] font-bold uppercase tracking-wider text-slate-500/75">Kritik Anomaliler</p>
          <p v-if="loading" class="mt-1 text-3xl font-black text-slate-300">—</p>
          <p v-else class="mt-1 text-3xl font-black" :class="criticalCount ? 'text-red-600' : 'text-slate-900'">
            {{ criticalCount ?? 0 }}
          </p>
          <p class="mt-1 text-xs" :class="criticalCount ? 'text-red-500/90' : 'text-slate-500/75'">
            {{ criticalCount ? 'Acil inceleme gerekiyor' : 'Güvenlik durumu normal' }}
          </p>
        </div>
        <span
          class="rf-icon-ring !h-14 !w-14"
          :class="criticalCount ? '!bg-red-100/80 !text-red-600 animate-flash' : ''"
        >
          <svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4a2 2 0 00-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" />
          </svg>
        </span>
      </div>
    </div>
  </div>
</template>
