<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useOverviewStore } from '../../stores/overviewStore.js'
import { useUiStore } from '../../stores/uiStore.js'
import { useVehicleStore } from '../../stores/vehicleStore.js'
import { formatNumber, formatTL } from '../../utils/format.js'
import { VEHICLE_STATUS_LABELS } from '../../utils/vehicleStatus.js'
import { ICON_PATHS } from '../../utils/iconPaths.js'
import FleetDonutChart from './FleetDonutChart.vue'
import RevenueLineChart from './RevenueLineChart.vue'
import NavigationLoadingOverlay from '../NavigationLoadingOverlay.vue'

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

// Donut segment renkleri, filo kartlarının aksan rengiyle bire bir eşleşir —
// gösterge ile kart arasında tutarlı bir renk dili kurar (rastgele gradyanlar yerine).
const donutSegments = computed(() => [
  { label: VEHICLE_STATUS_LABELS.RENTED, value: fleet.value.kirada, color: '#6366f1' },
  { label: VEHICLE_STATUS_LABELS.AVAILABLE, value: fleet.value.musait, color: '#06b6d4' },
  { label: VEHICLE_STATUS_LABELS.MAINTENANCE, value: fleet.value.bakimda, color: '#f43f5e' },
])

const fleetCards = computed(() => [
  { key: 'toplam', label: 'Filo Büyüklüğü', value: fleet.value.toplam, accent: null },
  { key: 'kirada', label: 'Kiradaki Araç', value: fleet.value.kirada, accent: '#6366f1' },
  { key: 'musait', label: 'Müsait Araç', value: fleet.value.musait, accent: '#06b6d4' },
  { key: 'bakimda', label: 'Bakımdaki Araç', value: fleet.value.bakimda, accent: '#f43f5e' },
])

// İkon path'leri statMeta ile aynı anahtarları (stat.anahtar) kullanır; salt
// sunum amaçlı, backend'den gelen veriyi veya hesaplama mantığını etkilemez.
const STAT_ICON_PATHS = {
  yillik_gider:
    'M2.25 6L9 12.75l4.306-4.306a11.95 11.95 0 015.814 5.518l2.74 1.22m0 0l-5.94 2.28m5.94-2.28l-2.28-5.941',
  yillik_gelir: ICON_PATHS.trendingUp,
  net_kar: ICON_PATHS.shieldCheck,
  kiralama_sayisi: ICON_PATHS.truck,
  kiralanan_gun: ICON_PATHS.calendar,
}

const statMeta = {
  yillik_gider: { accent: '#ea580c', tint: 'rgba(234, 88, 12, 0.1)' },
  yillik_gelir: { accent: '#0891b2', tint: 'rgba(8, 145, 178, 0.1)' },
  net_kar: { accent: '#059669', tint: 'rgba(5, 150, 105, 0.1)' },
  kiralama_sayisi: { accent: '#d97706', tint: 'rgba(217, 119, 6, 0.1)' },
  kiralanan_gun: { accent: '#e11d48', tint: 'rgba(225, 29, 72, 0.1)' },
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
  if (year !== selectedYear.value) {
    void overview.setYear(year)
  }
}

// "Aylık Gelir Trendi" başlığının yanındaki dinamik dönem etiketi — gerçek
// takvim ayını gösterir (seçili istatistik yılından bağımsız).
const currentPeriodLabel = computed(() => {
  const now = new Date()
  const month = new Intl.DateTimeFormat('tr-TR', { month: 'long' }).format(now)
  return `${month.charAt(0).toLocaleUpperCase('tr')}${month.slice(1)}`
})
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
      <!-- Hero: markanın kendi diagonal-kesim imzasını (rf-slant) kullanır,
           jenerik bulanık-baloncuk yerine. Canlı filo sayısı burada tek bakışta
           görünür (sayfanın "tez"i: şu an elimizde ne var). -->
      <section class="rf-hero relative overflow-hidden rounded-3xl shadow-2xl shadow-indigo-200/30">
        <div class="rf-hero-slant absolute inset-y-0 right-0 w-2/5" />

        <div class="relative flex flex-col gap-6 p-6 sm:flex-row sm:items-center sm:justify-between lg:p-8">
          <div class="flex items-center gap-5">
            <div
              v-if="company.logo_url"
              class="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white/90 p-2 shadow-xl ring-1 ring-white/60 backdrop-blur-sm"
            >
              <img :src="company.logo_url" :alt="company.ticari_unvan" class="max-h-full max-w-full object-contain" />
            </div>
            <div
              v-else
              class="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 font-display text-2xl font-black text-white shadow-xl"
            >
              {{ company.ticari_unvan?.slice(0, 2)?.toUpperCase() }}
            </div>
            <div>
              <p class="text-xs font-bold uppercase tracking-[0.25em] text-violet-600/80">Hoş geldiniz</p>
              <h2 class="font-display text-3xl font-black tracking-tight text-slate-900 lg:text-4xl">{{ company.ticari_unvan }}</h2>
            </div>
          </div>

          <div class="rf-hero-stat relative flex items-center gap-4 self-start rounded-2xl bg-white/70 px-5 py-4 shadow-lg ring-1 ring-white/70 backdrop-blur-sm sm:self-auto">
            <span class="rf-live-dot" aria-hidden="true" />
            <div>
              <p class="text-[11px] font-bold uppercase tracking-[0.2em] text-slate-400">Aktif Filo</p>
              <p class="font-display text-3xl font-black tabular-nums leading-none text-slate-900">{{ fleet.toplam }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- Filo durumu + grafik -->
      <section class="rf-glass-card overflow-hidden rounded-3xl p-6 lg:p-8">
        <div class="rf-section-head mb-6 flex items-center justify-between">
          <h3 class="font-display text-lg font-black text-slate-900">Filo Durumu</h3>
          <span class="inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-600 ring-1 ring-indigo-100">
            <span class="rf-live-dot rf-live-dot--sm" aria-hidden="true" />
            Canlı
          </span>
        </div>

        <div class="grid items-center gap-8 xl:grid-cols-2">
          <FleetDonutChart :segments="donutSegments" :size="260" />

          <div class="grid grid-cols-2 gap-3">
            <div
              v-for="card in fleetCards"
              :key="card.key"
              class="rf-metric-card group relative overflow-hidden rounded-2xl p-5 transition duration-300 hover:-translate-y-1"
              :class="card.accent ? 'rf-metric-card--tinted' : 'rf-metric-card--solid'"
              :style="card.accent ? { '--rf-metric-accent': card.accent } : undefined"
            >
              <p class="text-[11px] font-bold uppercase tracking-wider" :class="card.accent ? 'text-slate-500' : 'text-white/70'">{{ card.label }}</p>
              <p
                class="mt-2 font-display text-4xl font-black tabular-nums"
                :class="card.accent ? 'text-slate-900' : 'text-white'"
              >
                {{ card.value }}
              </p>
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
            <p class="relative font-display text-base font-bold">{{ item.title }}</p>
            <p class="relative mt-1 text-xs opacity-80">{{ item.desc }}</p>
          </button>
        </div>
      </section>

      <!-- İşletme istatistikleri — sadece 5 kalem -->
      <section class="rf-glass-card rounded-3xl p-6 lg:p-8">
        <div class="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 class="font-display text-xl font-black text-slate-900">İşletme İstatistikleri</h3>
            <p class="mt-1 text-sm text-slate-500">Yıllık finansal performans</p>
          </div>

          <div class="flex flex-wrap gap-2">
            <button
              v-for="y in years"
              :key="y"
              type="button"
              class="cursor-pointer rounded-xl px-4 py-2 text-sm font-bold tabular-nums transition-all duration-200"
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
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <div
              v-for="stat in stats"
              :key="stat.anahtar"
              class="rf-stat-card group relative overflow-hidden rounded-2xl bg-white/80 p-5 ring-1 ring-slate-100 transition duration-300 hover:-translate-y-1 hover:shadow-lg"
              :style="{ '--rf-stat-accent': statMeta[stat.anahtar]?.accent, '--rf-stat-tint': statMeta[stat.anahtar]?.tint }"
            >
              <span class="rf-stat-card-bar absolute inset-y-0 left-0 w-1" aria-hidden="true" />
              <div class="mb-3 flex items-center justify-between pl-2">
                <span class="rf-stat-icon flex h-9 w-9 items-center justify-center rounded-xl">
                  <svg class="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round" :d="STAT_ICON_PATHS[stat.anahtar]" />
                  </svg>
                </span>
                <span class="rounded-full bg-slate-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-400">
                  {{ selectedYear }}
                </span>
              </div>
              <p class="pl-2 text-xs font-bold uppercase tracking-wide text-slate-500">{{ stat.etiket }}</p>
              <p class="mt-1 pl-2 font-display text-2xl font-black tabular-nums text-slate-900">
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
              <h4 class="font-display font-bold text-slate-900">Aylık Gelir Trendi</h4>
              <span class="rounded-full bg-slate-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-slate-400 ring-1 ring-slate-100">
                {{ currentPeriodLabel }}
              </span>
            </div>
            <RevenueLineChart :data="monthlyRevenue" :height="180" />
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

/* Uygulamanın diğer yerlerinde de kullanılan diagonal-kesim imzası (bkz.
   .rf-slant-top / .rf-login-hero) — jenerik bulanık baloncuklar yerine. */
.rf-hero-slant {
  clip-path: polygon(28% 0, 100% 0, 100% 100%, 0% 100%);
  background: linear-gradient(160deg, color-mix(in srgb, var(--primary-color) 16%, transparent) 0%, color-mix(in srgb, var(--secondary-color) 10%, transparent) 100%);
  pointer-events: none;
}

.rf-glass-card {
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow:
    0 4px 24px rgba(99, 102, 241, 0.08),
    0 1px 3px rgba(15, 23, 42, 0.04);
  backdrop-filter: blur(16px);
}

/* --- Filo kartları: toplam = koyu imza kart, diğerleri donut segment
   renkleriyle eşleşen sakin aksan kartları. --- */
.rf-metric-card--solid {
  background: linear-gradient(150deg, #0f172a 0%, #1e293b 100%);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.22);
}

.rf-metric-card--tinted {
  background: color-mix(in srgb, var(--rf-metric-accent) 7%, white);
  border: 1px solid color-mix(in srgb, var(--rf-metric-accent) 18%, white);
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
}

.rf-metric-card--tinted::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--rf-metric-accent);
}

/* --- İstatistik kartları: nötr zemin, sol aksan çubuğu + tonlu ikon rozeti. --- */
.rf-stat-card-bar {
  background: var(--rf-stat-accent);
  opacity: 0.85;
}

.rf-stat-icon {
  background: var(--rf-stat-tint);
  color: var(--rf-stat-accent);
}

.rf-hero-stat {
  border: 1px solid rgba(255, 255, 255, 0.7);
}

.rf-live-dot--sm {
  height: 0.4rem;
  width: 0.4rem;
}
</style>
