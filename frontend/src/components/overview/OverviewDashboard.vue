<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useOverviewStore } from '../../stores/overviewStore.js'
import { useUiStore } from '../../stores/uiStore.js'
import { useVehicleStore } from '../../stores/vehicleStore.js'
import { formatNumber, formatTL } from '../../utils/format.js'
import { VEHICLE_STATUS_LABELS } from '../../utils/vehicleStatus.js'
import FleetDonutChart from './FleetDonutChart.vue'
import RevenueBarChart from './RevenueBarChart.vue'
import NavigationLoadingOverlay from './NavigationLoadingOverlay.vue'

const props = defineProps({
  navigate: { type: Function, required: true },
})

const overview = useOverviewStore()
const ui = useUiStore()
const vehicleStore = useVehicleStore()
const { stats, monthlyRevenue } = storeToRefs(overview)
const navLoading = ref(null)

onMounted(async () => {
  void vehicleStore.fetchVehicles()
  await overview.fetchOverview({ force: true })
})

const company = computed(() => overview.data?.sirket ?? null)
const years = computed(() => overview.data?.yillar ?? [new Date().getFullYear()])
const selectedYear = computed(() => overview.data?.yil ?? overview.selectedYear)

const fleet = computed(() => {
  const apiFleet = overview.data?.filo_durumu
  if (apiFleet) return apiFleet
  const c = vehicleStore.statusCounts
  return {
    toplam: c.total,
    kirada: c.RENTED,
    musait: c.AVAILABLE,
    bakimda: c.MAINTENANCE,
  }
})

const donutSegments = computed(() => [
  { label: VEHICLE_STATUS_LABELS.RENTED, value: fleet.value.kirada, color: '#6366f1' },
  { label: VEHICLE_STATUS_LABELS.AVAILABLE, value: fleet.value.musait, color: '#06b6d4' },
  { label: VEHICLE_STATUS_LABELS.MAINTENANCE, value: fleet.value.bakimda, color: '#f43f5e' },
])

const fleetCards = computed(() => [
  { key: 'toplam', label: 'Filo Büyüklüğü', value: fleet.value.toplam, gradient: 'from-slate-800 to-slate-950', glow: 'shadow-slate-300/30' },
  { key: 'kirada', label: 'Kiradaki Araç', value: fleet.value.kirada, gradient: 'from-indigo-500 to-violet-600', glow: 'shadow-indigo-300/40' },
  { key: 'musait', label: 'Müsait Araç', value: fleet.value.musait, gradient: 'from-cyan-400 to-teal-500', glow: 'shadow-cyan-300/40' },
  { key: 'bakimda', label: 'Bakımdaki Araç', value: fleet.value.bakimda, gradient: 'from-rose-400 to-pink-500', glow: 'shadow-rose-300/40' },
])

const statMeta = {
  net_kazanc: { icon: '💰', gradient: 'from-violet-500/10 to-violet-600/5', accent: 'text-violet-600', ring: 'ring-violet-200' },
  yillik_gelir: { icon: '📈', gradient: 'from-cyan-500/10 to-cyan-600/5', accent: 'text-cyan-600', ring: 'ring-cyan-200' },
  net_kar: { icon: '✨', gradient: 'from-emerald-500/10 to-emerald-600/5', accent: 'text-emerald-600', ring: 'ring-emerald-200' },
  kiralama_sayisi: { icon: '🚗', gradient: 'from-amber-500/10 to-amber-600/5', accent: 'text-amber-600', ring: 'ring-amber-200' },
  kiralanan_gun: { icon: '📅', gradient: 'from-rose-500/10 to-rose-600/5', accent: 'text-rose-600', ring: 'ring-rose-200' },
}

const shortcuts = [
  {
    id: 'ai',
    title: 'AI Filo Danışmanı',
    desc: 'Fiyat, bakım ve operasyon soruları',
    action: () => ui.openAiChat(),
    gradient: 'from-slate-900 via-indigo-950 to-violet-950',
    icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4-.8L3 20l1.3-3.2A7.96 7.96 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
  },
  {
    id: 'live',
    title: 'Canlı Takip',
    desc: 'Haritada gerçek zamanlı izleme',
    action: () => props.navigate('live'),
    gradient: 'from-cyan-500 to-teal-600',
    icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z',
  },
  {
    id: 'vehicles',
    title: 'Araçlar',
    desc: 'Filo listesi ve maliyetler',
    action: () => props.navigate('vehicles'),
    gradient: 'from-violet-500 to-purple-600',
    icon: 'M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1',
  },
  {
    id: 'drivers',
    title: 'Sürücüler',
    desc: 'Müşteri profilleri ve geçmiş',
    action: () => props.navigate('drivers'),
    gradient: 'from-amber-400 to-orange-500',
    icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
  },
]

function formatStatValue(stat) {
  const value = stat.deger
  if (value === null || value === undefined) return '—'
  if (stat.birim === 'TL') return formatTL(value)
  if (stat.birim === 'adet' || stat.birim === 'gün') return formatNumber(value)
  return formatNumber(value)
}

function handleShortcut(item) {
  if (navLoading.value) return
  navLoading.value = { id: item.id, title: item.title }
  window.setTimeout(() => {
    item.action()
    navLoading.value = null
  }, 1000)
}

function selectYear(year) {
  if (year !== selectedYear.value) void overview.setYear(year)
}
</script>

<template>
  <div class="rf-home space-y-6">
    <NavigationLoadingOverlay
      v-if="navLoading"
      :title="navLoading.title"
      subtitle="Bir saniye, hazırlanıyor…"
    />

    <div v-if="overview.loading && !company" class="grid place-items-center py-28">
      <div class="h-14 w-14 animate-spin rounded-full border-[3px] border-white border-t-violet-500 shadow-lg" />
      <p class="mt-5 text-sm font-semibold text-slate-500">Ev sayfası yükleniyor…</p>
    </div>

    <div v-else-if="overview.error && !company" class="rounded-2xl border border-red-200/80 bg-red-50/80 px-6 py-12 text-center shadow-lg backdrop-blur-sm">
      <p class="text-lg font-bold text-red-800">Özet yüklenemedi</p>
      <button
        type="button"
        class="mt-4 cursor-pointer rounded-xl bg-red-600 px-6 py-2.5 text-sm font-bold text-white shadow-lg transition hover:bg-red-700"
        @click="overview.fetchOverview({ force: true })"
      >
        Tekrar dene
      </button>
    </div>

    <template v-else-if="company">
      <!-- Hero -->
      <section class="rf-hero relative overflow-hidden rounded-3xl p-6 shadow-2xl shadow-indigo-200/30 lg:p-8">
        <div class="pointer-events-none absolute -left-16 -top-16 h-56 w-56 rounded-full bg-violet-400/30 blur-3xl" />
        <div class="pointer-events-none absolute -bottom-20 -right-10 h-64 w-64 rounded-full bg-cyan-400/25 blur-3xl" />

        <div class="relative flex items-center gap-5">
          <div
            v-if="company.logo_url"
            class="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white/90 p-2 shadow-xl ring-1 ring-white/60 backdrop-blur-sm"
          >
            <img :src="company.logo_url" :alt="company.ticari_unvan" class="max-h-full max-w-full object-contain" />
          </div>
          <div
            v-else
            class="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 text-2xl font-black text-white shadow-xl"
          >
            {{ company.ticari_unvan?.slice(0, 2)?.toUpperCase() }}
          </div>
          <div>
            <p class="text-xs font-bold uppercase tracking-[0.25em] text-violet-600/80">Hoş geldiniz</p>
            <h2 class="text-3xl font-black tracking-tight text-slate-900 lg:text-4xl">{{ company.ticari_unvan }}</h2>
          </div>
        </div>
      </section>

      <!-- Filo durumu + grafik -->
      <section class="rf-glass-card overflow-hidden rounded-3xl p-6 lg:p-8">
        <div class="mb-6 flex items-center justify-between">
          <h3 class="text-lg font-black text-slate-900">Filo Durumu</h3>
          <span class="rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-600 ring-1 ring-indigo-100">
            Canlı
          </span>
        </div>

        <div class="grid items-center gap-8 xl:grid-cols-2">
          <FleetDonutChart :segments="donutSegments" :size="260" />

          <div class="grid grid-cols-2 gap-3">
            <div
              v-for="card in fleetCards"
              :key="card.key"
              class="group relative overflow-hidden rounded-2xl bg-gradient-to-br p-5 text-white shadow-xl transition duration-300 hover:-translate-y-1 hover:shadow-2xl"
              :class="[card.gradient, card.glow]"
            >
              <div class="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-white/15 blur-2xl transition group-hover:scale-125" />
              <p class="text-[11px] font-bold uppercase tracking-wider opacity-75">{{ card.label }}</p>
              <p class="mt-2 text-4xl font-black">{{ card.value }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Hızlı erişim -->
      <section>
        <h3 class="mb-4 text-sm font-black uppercase tracking-[0.2em] text-slate-400">Hızlı Erişim</h3>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <button
            v-for="item in shortcuts"
            :key="item.id"
            type="button"
            class="rf-shortcut group relative cursor-pointer overflow-hidden rounded-2xl bg-gradient-to-br p-5 text-left text-white shadow-xl transition-all duration-300 hover:-translate-y-2 hover:shadow-2xl active:scale-[0.98]"
            :class="item.gradient"
            @click="handleShortcut(item)"
          >
            <div class="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/20 to-transparent opacity-0 transition group-hover:opacity-100" />
            <div class="relative mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-white/20 backdrop-blur-sm">
              <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
              </svg>
            </div>
            <p class="relative text-base font-bold">{{ item.title }}</p>
            <p class="relative mt-1 text-xs opacity-80">{{ item.desc }}</p>
          </button>
        </div>
      </section>

      <!-- İşletme istatistikleri — sadece 5 kalem -->
      <section class="rf-glass-card rounded-3xl p-6 lg:p-8">
        <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="text-xl font-black text-slate-900">İşletme İstatistikleri</h3>
            <p class="mt-1 text-sm text-slate-500">Yıllık finansal performans</p>
          </div>

          <div class="flex flex-wrap gap-2">
            <button
              v-for="y in years"
              :key="y"
              type="button"
              class="cursor-pointer rounded-xl px-4 py-2 text-sm font-bold transition-all duration-200"
              :class="y === selectedYear
                ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-200'
                : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:ring-violet-300 hover:text-violet-700'"
              :disabled="overview.loading"
              @click="selectYear(y)"
            >
              {{ y }}
            </button>
          </div>
        </div>

        <div v-if="overview.loading" class="grid place-items-center py-16">
          <div class="h-10 w-10 animate-spin rounded-full border-[3px] border-slate-200 border-t-violet-500" />
        </div>

        <template v-else>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <div
              v-for="stat in stats"
              :key="stat.anahtar"
              class="group relative overflow-hidden rounded-2xl bg-gradient-to-br p-5 shadow-md ring-1 transition duration-300 hover:-translate-y-1 hover:shadow-xl"
              :class="[statMeta[stat.anahtar]?.gradient, statMeta[stat.anahtar]?.ring]"
            >
              <div class="mb-3 flex items-center justify-between">
                <span class="text-2xl">{{ statMeta[stat.anahtar]?.icon }}</span>
                <span
                  class="rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-400"
                >
                  {{ selectedYear }}
                </span>
              </div>
              <p class="text-xs font-bold uppercase tracking-wide text-slate-500">{{ stat.etiket }}</p>
              <p class="mt-2 text-2xl font-black text-slate-900" :class="statMeta[stat.anahtar]?.accent">
                {{ formatStatValue(stat) }}
                <span
                  v-if="stat.birim && stat.birim !== 'TL'"
                  class="text-sm font-semibold text-slate-400"
                >
                  {{ stat.birim }}
                </span>
              </p>
            </div>
          </div>

          <!-- Aylık gelir grafiği -->
          <div class="mt-8 rounded-2xl bg-white/70 p-5 ring-1 ring-slate-100 backdrop-blur-sm">
            <div class="mb-4 flex items-center justify-between">
              <div>
                <h4 class="font-bold text-slate-900">Aylık Gelir Trendi</h4>
                <p class="text-xs text-slate-500">{{ selectedYear }} yılı kırılımı</p>
              </div>
            </div>
            <RevenueBarChart :data="monthlyRevenue" :height="180" />
          </div>
        </template>
      </section>
    </template>
  </div>
</template>

<style scoped>
.rf-hero {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(238, 242, 255, 0.9) 50%, rgba(236, 254, 255, 0.85) 100%);
  border: 1px solid rgba(255, 255, 255, 0.8);
}

.rf-glass-card {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow:
    0 4px 24px rgba(99, 102, 241, 0.08),
    0 1px 3px rgba(15, 23, 42, 0.04);
  backdrop-filter: blur(16px);
}
</style>
