<script setup>
// Otomatik piyasa fiyat karşılaştırması + AI akıllı fiyat (Filo Müdürü).
import { computed, onMounted, ref, watch } from 'vue'
import { useVehicleStore } from '../stores/vehicleStore.js'

const store = useVehicleStore()

const selectedVehicleId = ref(null)

const priceFormatter = new Intl.NumberFormat('tr-TR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const kmFormatter = new Intl.NumberFormat('tr-TR')

const vehicles = computed(() => store.vehicles)
const loading = computed(() => store.loading)
const marketSyncing = computed(() => store.marketSyncing)

const selectedVehicle = computed(() =>
  vehicles.value.find((v) => v.id === selectedVehicleId.value) ?? null,
)

const marketAdvice = computed(() => {
  const id = selectedVehicleId.value
  if (!id) return null
  return store.marketPricingById[id] ?? null
})

const marketListings = computed(() => {
  const id = selectedVehicleId.value
  if (!id) return []
  return store.marketListingsById[id] ?? []
})

const marketMeta = computed(() => {
  const id = selectedVehicleId.value
  if (!id) return null
  return store.marketMetaById[id] ?? null
})

const marketStatistics = computed(() => {
  const id = selectedVehicleId.value
  if (!id) return null
  return store.marketStatisticsById[id] ?? null
})

function formatPrice(value) {
  return value != null ? `${priceFormatter.format(value)} TL` : '—'
}

async function loadVehicleData(vehicleId) {
  if (!vehicleId) return
  await Promise.all([
    store.fetchVehiclePricing(vehicleId, true),
    store.fetchCompetitorPrices(vehicleId),
  ])
}

watch(selectedVehicleId, (id) => {
  if (id && !store.marketSyncing) loadVehicleData(id)
})

onMounted(async () => {
  if (!store.vehicles.length) await store.fetchVehicles()
  await store.syncFleetMarketPrices()
  if (store.vehicles.length && !selectedVehicleId.value) {
    selectedVehicleId.value = store.vehicles[0].id
  }
  if (selectedVehicleId.value) {
    await loadVehicleData(selectedVehicleId.value)
  }
})
</script>

<template>
  <div class="space-y-6">
    <div class="rounded-xl border border-brand-100 bg-gradient-to-r from-brand-50 to-indigo-50 px-5 py-4">
      <h3 class="text-sm font-bold text-slate-800">Akıllı Fiyatlandırma</h3>
      <p class="mt-1 text-sm text-slate-600">
        Araç seçin; sistem Enuygun API üzerinden aynı segmentteki tüm kiralama firmalarının
        günlük fiyatlarını listeler ve AI önerisi üretir.
      </p>
    </div>

    <div
      v-if="marketSyncing"
      class="flex items-center gap-3 rounded-xl border border-brand-100 bg-white px-5 py-4"
    >
      <div class="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600"></div>
      <p class="text-sm text-slate-600">Enuygun API üzerinden filo piyasa fiyatları güncelleniyor...</p>
    </div>

    <div v-if="loading && !vehicles.length" class="grid place-items-center rounded-2xl border border-slate-200 bg-white p-16">
      <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
      <p class="mt-3 text-sm text-slate-500">Araçlar yükleniyor...</p>
    </div>

    <template v-else>
      <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <label class="text-xs font-semibold uppercase tracking-wide text-slate-400">Araç Seçin</label>
        <select
          v-model="selectedVehicleId"
          class="mt-2 w-full max-w-xl rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-800 outline-none focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-100"
          :disabled="marketSyncing"
        >
          <option v-for="v in vehicles" :key="v.id" :value="v.id">
            {{ v.plate_number }} — {{ v.brand }} {{ v.model }}
            <template v-if="v.sipp_code"> ({{ v.sipp_code }})</template>
          </option>
        </select>
        <p v-if="selectedVehicle" class="mt-2 text-sm text-slate-500">
          {{ selectedVehicle.brand }} {{ selectedVehicle.model }}
          <span v-if="selectedVehicle.sinif_etiketi">· {{ selectedVehicle.sinif_etiketi }}</span>
          · {{ kmFormatter.format(selectedVehicle.current_km) }} km
        </p>
        <p v-if="marketMeta?.matchedSegment" class="mt-2 text-xs text-brand-700">
          Segment: {{ marketMeta.matchedSegment }}
          <span v-if="marketMeta.vehicleCount"> · {{ marketMeta.vehicleCount }} teklif</span>
        </p>
        <p v-if="marketMeta?.arama" class="mt-1 text-xs text-slate-400">
          {{ marketMeta.arama.sehir }} · {{ marketMeta.arama.alis_tarihi }} → {{ marketMeta.arama.donus_tarihi }}
        </p>
      </div>

      <div v-if="selectedVehicleId && !marketSyncing" class="grid gap-6 xl:grid-cols-2">
        <div class="rounded-2xl border border-emerald-100 bg-white shadow-sm">
          <div class="border-b border-emerald-100 bg-emerald-50/50 px-5 py-3">
            <h4 class="text-sm font-bold text-emerald-900">Piyasa Karşılaştırması</h4>
            <p class="text-xs text-emerald-700">Enuygun — segment uyumlu tüm firmalar</p>
          </div>
          <div
            v-if="marketStatistics"
            class="grid grid-cols-3 gap-2 border-b border-emerald-100 bg-emerald-50/30 px-5 py-3 text-center text-xs"
          >
            <div>
              <p class="text-slate-500">Min</p>
              <p class="font-bold text-emerald-900">{{ formatPrice(marketStatistics.minPrice) }}</p>
            </div>
            <div>
              <p class="text-slate-500">Ortalama</p>
              <p class="font-bold text-emerald-900">{{ formatPrice(marketStatistics.averagePrice) }}</p>
            </div>
            <div>
              <p class="text-slate-500">Max</p>
              <p class="font-bold text-emerald-900">{{ formatPrice(marketStatistics.maxPrice) }}</p>
            </div>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-sm">
              <thead class="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th class="px-5 py-3 font-semibold">Firma</th>
                  <th class="px-5 py-3 font-semibold">Araç</th>
                  <th class="px-5 py-3 font-semibold">SIPP</th>
                  <th class="px-5 py-3 font-semibold text-right">Günlük Fiyat</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100">
                <tr v-if="!marketListings.length">
                  <td colspan="4" class="px-5 py-10 text-center text-slate-400">
                    Piyasa verisi henüz yok. Senkron tamamlanınca burada görünecek.
                  </td>
                </tr>
                <tr v-for="(row, idx) in marketListings" :key="`${row.kaynak}-${idx}`" class="hover:bg-slate-50/80">
                  <td class="px-5 py-3 font-medium text-slate-800">{{ row.kaynak || row.provider }}</td>
                  <td class="px-5 py-3 text-slate-600">{{ row.benzer_arac || `${row.brand} ${row.model}` }}</td>
                  <td class="px-5 py-3 font-mono text-xs text-slate-500">{{ row.segment || '—' }}</td>
                  <td class="px-5 py-3 text-right font-bold text-emerald-800">{{ formatPrice(row.gunluk_fiyat ?? row.dailyPrice) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="space-y-4">
          <div class="rounded-2xl border-2 border-brand-200 bg-gradient-to-br from-white to-brand-50 p-6 shadow-sm">
            <p class="text-xs font-bold uppercase tracking-widest text-brand-600">Önerilen Akıllı Fiyat</p>
            <p class="mt-3 text-5xl font-black tracking-tight text-brand-700 sm:text-6xl">
              {{ marketAdvice ? formatPrice(marketAdvice.onerilen_fiyat) : '—' }}
            </p>
            <p v-if="marketAdvice?.piyasa_ortalamasi" class="mt-2 text-sm text-slate-600">
              Piyasa ortalaması:
              <span class="font-semibold text-slate-800">{{ formatPrice(marketAdvice.piyasa_ortalamasi) }}</span>
              <span class="text-slate-400"> · {{ marketAdvice.rakip_sayisi }} kaynak</span>
            </p>
          </div>

          <div class="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-5">
            <div class="flex items-start gap-3">
              <div class="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-indigo-600 text-lg text-white">AI</div>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-bold text-indigo-900">AI Tavsiyesi</p>
                <p class="mt-2 text-sm leading-relaxed text-indigo-950">
                  {{ marketAdvice?.ai_tavsiyesi ?? 'Araç seçildiğinde öneri yüklenecek.' }}
                </p>
              </div>
            </div>
          </div>

          <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p class="text-xs font-bold uppercase tracking-wide text-slate-400">Gerekçe</p>
            <p class="mt-2 text-sm leading-relaxed text-slate-700">
              {{ marketAdvice?.gerekce ?? '—' }}
            </p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
