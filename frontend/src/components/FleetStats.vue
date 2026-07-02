<script setup>
// Filo istatistikleri — 4 kurumsal metrik kartı (Day 11).
// Veriyi store.fleetAnalytics'ten okur; toplam/doluluk için store'daki araç
// listesinden anlık fallback kullanır (analitik yüklenene kadar boş kalmaz).
import { computed, onMounted } from 'vue'
import { useVehicleStore } from '../stores/vehicleStore.js'

const store = useVehicleStore()

onMounted(() => store.fetchFleetAnalytics())

const a = computed(() => store.fleetAnalytics)

// Toplam araç (analitik yoksa yüklenmiş araç listesinden).
const totalVehicles = computed(() => a.value?.toplam_arac ?? store.statusCounts.total)

// Doluluk oranı (analitik yoksa store sayımlarından hesaplanır).
const occupancy = computed(() => {
  if (a.value) return a.value.doluluk_orani
  const { total, RENTED } = store.statusCounts
  return total ? Math.round((RENTED / total) * 1000) / 10 : 0
})

const criticalCount = computed(() => a.value?.aktif_kritik_anomali ?? null)
const avgScore = computed(() => a.value?.ortalama_surus_skoru ?? null)

// Ortalama skora göre renk (yeşil > 80, turuncu 70-80, kırmızı < 70).
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
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
    <!-- Toplam Araç -->
    <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div class="flex items-center justify-between">
        <p class="text-sm font-medium text-slate-500">Toplam Araç</p>
        <span class="grid h-9 w-9 place-items-center rounded-lg bg-slate-100 text-slate-600">
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1" />
          </svg>
        </span>
      </div>
      <p class="mt-3 text-3xl font-bold text-slate-900">{{ totalVehicles }}</p>
      <p class="mt-1 text-xs text-slate-400">Filodaki tüm araçlar</p>
    </div>

    <!-- Filo Doluluk Oranı -->
    <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div class="flex items-center justify-between">
        <p class="text-sm font-medium text-slate-500">Filo Doluluk Oranı</p>
        <span class="grid h-9 w-9 place-items-center rounded-lg bg-blue-50 text-blue-600">
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
        </span>
      </div>
      <p class="mt-3 text-3xl font-bold text-blue-600">%{{ occupancy }}</p>
      <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div class="h-full rounded-full bg-blue-500 transition-all" :style="{ width: Math.min(100, occupancy) + '%' }"></div>
      </div>
    </div>

    <!-- Aktif Kritik Anomaliler -->
    <div
      class="rounded-2xl border p-5 shadow-sm"
      :class="criticalCount ? 'border-red-200 bg-red-50' : 'border-slate-200 bg-white'"
    >
      <div class="flex items-center justify-between">
        <p class="text-sm font-medium text-slate-500">Aktif Kritik Anomaliler</p>
        <span
          class="grid h-9 w-9 place-items-center rounded-lg"
          :class="criticalCount ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-600'"
        >
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4a2 2 0 00-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" />
          </svg>
        </span>
      </div>
      <p v-if="loading" class="mt-3 text-3xl font-bold text-slate-300">—</p>
      <p v-else class="mt-3 text-3xl font-bold" :class="criticalCount ? 'text-red-600' : 'text-slate-900'">
        {{ criticalCount ?? 0 }}
      </p>
      <p class="mt-1 text-xs" :class="criticalCount ? 'text-red-500' : 'text-slate-400'">
        {{ criticalCount ? 'Acil inceleme gerekiyor' : 'Güvenlik durumu normal' }}
      </p>
    </div>

    <!-- Ortalama Sürücü Skoru -->
    <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div class="flex items-center justify-between">
        <p class="text-sm font-medium text-slate-500">Ortalama Sürücü Skoru</p>
        <span class="grid h-9 w-9 place-items-center rounded-lg bg-emerald-50 text-emerald-600">
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
            <path stroke-linecap="round" stroke-linejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.196-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118L2.07 9.801c-.783-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
          </svg>
        </span>
      </div>
      <p v-if="loading" class="mt-3 text-3xl font-bold text-slate-300">—</p>
      <p v-else class="mt-3 text-3xl font-bold" :class="scoreAccent">
        {{ avgScore ?? '—' }}<span class="text-lg text-slate-400">/100</span>
      </p>
      <p class="mt-1 text-xs text-slate-400">Filo geneli sürüş kalitesi</p>
    </div>
  </div>
</template>
