<script setup>
// Fiyatlandırma: Enuygun piyasa verisi + maliyet tabanlı fiyat önerisi yan yana.
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useVehicleStore } from '../stores/vehicleStore.js'
import { useFinanceStore } from '../stores/financeStore.js'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'
import { useDriverStore } from '../stores/driverStore.js'
import { useUiStore } from '../stores/uiStore.js'
import { useAuthStore } from '../stores/authStore.js'
import PricingCostPanel from './finance/PricingCostPanel.vue'
import VehicleFormModal from './VehicleFormModal.vue'
import RentalWorkflowProgress from './RentalWorkflowProgress.vue'

const store = useVehicleStore()
const finance = useFinanceStore()
const workflow = useRentalWorkflowStore()
const { readyForDriverPick } = storeToRefs(workflow)
const driverStore = useDriverStore()
const ui = useUiStore()
const auth = useAuthStore()

const selectedVehicleId = ref(null)
const dateMode = ref('default')
const customPickup = ref('')
const customDropoff = ref('')
const dateError = ref('')

const showEditModal = ref(false)
const editProfile = ref(null)

const priceFormatter = new Intl.NumberFormat('tr-TR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})
const kmFormatter = new Intl.NumberFormat('tr-TR')
const displayDateFormatter = new Intl.DateTimeFormat('tr-TR', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

function addDays(base, days) {
  const d = new Date(base)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

const minPickupDate = addDays(new Date(), 1)

function initCustomDates() {
  if (!customPickup.value) customPickup.value = addDays(new Date(), 30)
  if (!customDropoff.value) customDropoff.value = addDays(new Date(), 33)
}

const vehicles = computed(() => store.vehicles)
const loading = computed(() => store.loading)

const dateParams = computed(() => {
  if (dateMode.value === 'default') return { baslangic: null, bitis: null }
  return { baslangic: customPickup.value, bitis: customDropoff.value }
})

const marketSlot = computed(() => {
  const id = selectedVehicleId.value
  if (!id) return null
  return store.marketSlotKey(id, dateParams.value.baslangic, dateParams.value.bitis)
})

const competitorLoading = computed(
  () => marketSlot.value && store.competitorLoadingId === marketSlot.value,
)

const selectedVehicle = computed(() =>
  vehicles.value.find((v) => v.id === selectedVehicleId.value) ?? null,
)

const marketListings = computed(() => {
  if (!marketSlot.value) return []
  return store.marketListingsById[marketSlot.value] ?? []
})

const marketMeta = computed(() => {
  if (!marketSlot.value) return null
  return store.marketMetaById[marketSlot.value] ?? null
})

const marketStatistics = computed(() => {
  if (!marketSlot.value) return null
  return store.marketStatisticsById[marketSlot.value] ?? null
})

const marketAverage = computed(() => marketStatistics.value?.averagePrice ?? null)

const costAnalysis = computed(() =>
  selectedVehicleId.value ? finance.quoteFor(selectedVehicleId.value) : null,
)

const rentalDays = computed(() => {
  if (costAnalysis.value?.kiralanan_gun) return costAnalysis.value.kiralanan_gun
  const arama = marketMeta.value?.arama
  if (arama?.alis_tarihi && arama?.donus_tarihi) {
    const ms = new Date(arama.donus_tarihi) - new Date(arama.alis_tarihi)
    return Math.max(Math.round(ms / 86400000), 1)
  }
  if (dateMode.value === 'custom' && customPickup.value && customDropoff.value) {
    const ms = new Date(customDropoff.value) - new Date(customPickup.value)
    return Math.max(Math.round(ms / 86400000), 1)
  }
  return 1
})

const isFutureWindow = computed(() => marketMeta.value?.arama?.varsayilan_pencere === false)

const windowLabel = computed(() => {
  const arama = marketMeta.value?.arama
  if (!arama) return null
  const pickup = arama.hedef_baslangic || arama.alis_tarihi
  const dropoff = arama.hedef_bitis || arama.donus_tarihi
  if (!pickup || !dropoff) return null
  try {
    const p = displayDateFormatter.format(new Date(`${pickup}T12:00:00`))
    const d = displayDateFormatter.format(new Date(`${dropoff}T12:00:00`))
    return `${p} → ${d}`
  } catch {
    return `${pickup} → ${dropoff}`
  }
})

function formatPrice(value) {
  return value != null ? `${priceFormatter.format(value)} TL` : '—'
}

function validateCustomDates() {
  dateError.value = ''
  if (dateMode.value !== 'custom') return true
  if (!customPickup.value || !customDropoff.value) {
    dateError.value = 'Alış ve dönüş tarihlerini seçin.'
    return false
  }
  if (customDropoff.value <= customPickup.value) {
    dateError.value = 'Dönüş tarihi alış tarihinden sonra olmalıdır.'
    return false
  }
  if (customPickup.value < minPickupDate) {
    dateError.value = 'Alış tarihi en erken yarın olabilir.'
    return false
  }
  return true
}

function loadVehicleData(vehicleId, { force = false } = {}) {
  if (!vehicleId || !validateCustomDates()) return
  const opts = dateParams.value
  void store.fetchCompetitorPrices(vehicleId, { force, ...opts })
  void finance.fetchRentalQuote(vehicleId, {
    force,
    baslangic: opts.baslangic,
    bitis: opts.bitis,
  })
}

function applyDateAnalysis() {
  if (!selectedVehicleId.value) return
  loadVehicleData(selectedVehicleId.value, { force: true })
}

function setDateMode(mode) {
  dateMode.value = mode
  if (mode === 'custom') initCustomDates()
  dateError.value = ''
  if (selectedVehicleId.value) {
    loadVehicleData(selectedVehicleId.value, { force: mode === 'custom' })
  }
}

async function openEditModal() {
  if (!selectedVehicle.value) return
  editProfile.value = await finance.fetchProfile(selectedVehicleId.value)
  showEditModal.value = true
}

async function onVehicleSaved() {
  showEditModal.value = false
  await store.fetchVehicles()
  if (selectedVehicleId.value) {
    await finance.fetchRentalQuote(selectedVehicleId.value, {
      force: true,
      ...dateParams.value,
    })
  }
}

watch(
  vehicles,
  (list) => {
    if (workflow.active && workflow.vehicleId) {
      selectedVehicleId.value = workflow.vehicleId
      return
    }
    if (list.length && !selectedVehicleId.value) {
      selectedVehicleId.value = list[0].id
    }
  },
  { immediate: true },
)

async function onOfferAccepted(price) {
  if (!selectedVehicle.value) return
  const pickup = dateMode.value === 'custom' ? customPickup.value : addDays(new Date(), 1)
  const dropoff = dateMode.value === 'custom' ? customDropoff.value : addDays(new Date(), 3)
  workflow.acceptPricingOffer({
    vehicle: selectedVehicle.value,
    agreedPrice: price,
    pickupDate: pickup,
    dropoffDate: dropoff,
  })
  ui.navigate('drivers', { isFleetManager: auth.isFleetManager })
  await nextTick()
  void driverStore.fetchDrivers()
}

watch(selectedVehicleId, (id) => {
  if (id) {
    loadVehicleData(id)
    if (workflow.active) {
      const v = vehicles.value.find((x) => x.id === id)
      if (v) workflow.selectVehicle(v)
    }
  }
})

onMounted(() => {
  if (!store.vehicles.length) void store.fetchVehicles()
})
</script>

<template>
  <div class="space-y-6">
    <RentalWorkflowProgress v-if="readyForDriverPick">
      <p class="mt-2 text-sm text-slate-600">
        Devam eden bir kiralama süreciniz var.
        <button
          type="button"
          class="font-bold text-brand-600 underline"
          @click="ui.navigate('drivers', { isFleetManager: auth.isFleetManager })"
        >
          Sürücü seçmeye git
        </button>
      </p>
    </RentalWorkflowProgress>

    <div class="rf-glass-strong rounded-3xl px-6 py-5">
      <h3 class="text-lg font-black text-slate-900">Akıllı Fiyatlandırma</h3>
      <p class="mt-1 text-sm text-slate-500/80">
        Sol tarafta Enuygun piyasa fiyatları, sağ tarafta seçilen gün sayısı için maliyet tabanınız
        ve müdür fiyatı. Tabanın altına inmeyin; piyasa ile dengeli fiyat belirleyin.
      </p>
    </div>

    <div v-if="loading && !vehicles.length" class="rf-glass grid place-items-center rounded-3xl p-16">
      <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
      <p class="mt-3 text-sm text-slate-500">Araçlar yükleniyor...</p>
    </div>

    <template v-else>
      <!-- Tarih penceresi -->
      <div class="rf-glass-strong rounded-3xl p-5">
        <label class="text-xs font-bold uppercase tracking-widest text-slate-500/75">Piyasa Tarih Penceresi</label>
        <div class="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            class="rf-pill-filter"
            :class="dateMode === 'default' ? 'rf-pill-filter--active' : 'rf-pill-filter--idle'"
            @click="setDateMode('default')"
          >
            Varsayılan (yarın + ertesi gün)
          </button>
          <button
            type="button"
            class="rf-pill-filter"
            :class="dateMode === 'custom' ? 'rf-pill-filter--active' : 'rf-pill-filter--idle'"
            @click="setDateMode('custom')"
          >
            Gelecek Tarih Analizi
          </button>
        </div>

        <div v-if="dateMode === 'custom'" class="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label class="text-xs font-medium text-slate-500/80">Alış Tarihi</label>
            <input
              v-model="customPickup"
              type="date"
              :min="minPickupDate"
              class="rf-input mt-1"
            />
          </div>
          <div>
            <label class="text-xs font-medium text-slate-500/80">Dönüş Tarihi</label>
            <input
              v-model="customDropoff"
              type="date"
              :min="customPickup || minPickupDate"
              class="rf-input mt-1"
            />
          </div>
          <div class="flex items-end">
            <button
              type="button"
              class="rf-btn-primary w-full"
              :disabled="competitorLoading"
              @click="applyDateAnalysis"
            >
              {{ competitorLoading ? 'Analiz ediliyor…' : 'Bu Tarihler İçin Analiz Et' }}
            </button>
          </div>
        </div>

        <p v-if="dateError" class="mt-2 text-sm text-red-600">{{ dateError }}</p>
      </div>

      <div class="rf-glass-strong rounded-3xl p-5">
        <label class="text-xs font-bold uppercase tracking-widest text-slate-500/75">Araç Seçin</label>
        <select
          v-model="selectedVehicleId"
          class="rf-input mt-2 max-w-xl"
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
        <div v-if="windowLabel" class="mt-3 flex flex-wrap items-center gap-2">
          <span
            class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold"
            :class="isFutureWindow
              ? 'bg-amber-100 text-amber-800 ring-1 ring-amber-200'
              : 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200'"
          >
            {{ isFutureWindow ? 'Gelecek tarih' : 'Varsayılan pencere' }}
          </span>
          <span class="text-xs text-slate-500">{{ marketMeta?.arama?.sehir }} · {{ windowLabel }}</span>
        </div>
      </div>

      <!-- Piyasa + Maliyet yan yana -->
      <div v-if="selectedVehicleId" class="grid gap-6 xl:grid-cols-2">
        <!-- Enuygun piyasa -->
        <div class="rf-glass-strong overflow-hidden rounded-3xl">
          <div class="border-b border-white/30 bg-white/20 px-5 py-4 backdrop-blur-sm">
            <div class="flex items-center gap-2">
              <span class="rf-live-dot" />
              <h4 class="text-sm font-black text-slate-900">Enuygun — Piyasa Karşılaştırması</h4>
            </div>
            <p class="text-xs text-slate-500/80">Rakip firmaların günlük fiyatları</p>
          </div>
          <div
            v-if="marketStatistics"
            class="grid grid-cols-3 gap-2 border-b border-white/20 bg-white/10 px-5 py-4 text-center text-xs backdrop-blur-sm"
          >
            <div class="rf-glass rounded-2xl px-2 py-2">
              <p class="text-slate-500/75">Min</p>
              <p class="font-black text-emerald-800">{{ formatPrice(marketStatistics.minPrice) }}</p>
            </div>
            <div class="rf-glass rounded-2xl px-2 py-2">
              <p class="text-slate-500/75">Ortalama</p>
              <p class="font-black text-emerald-800">{{ formatPrice(marketStatistics.averagePrice) }}</p>
            </div>
            <div class="rf-glass rounded-2xl px-2 py-2">
              <p class="text-slate-500/75">Max</p>
              <p class="font-black text-emerald-800">{{ formatPrice(marketStatistics.maxPrice) }}</p>
            </div>
          </div>
          <div class="p-4">
            <div v-if="competitorLoading && !marketListings.length" class="grid place-items-center py-12 text-slate-500">
              <span class="inline-flex items-center gap-2 text-sm">
                <span class="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600" />
                Piyasa verisi yükleniyor…
              </span>
            </div>
            <p v-else-if="!marketListings.length" class="py-10 text-center text-sm text-slate-400">
              Bu araç için piyasa verisi yok.
              <code class="mt-1 block text-xs">python manage.py fetch_competitor_prices</code>
            </p>
            <div v-else class="grid gap-3 sm:grid-cols-2">
              <div
                v-for="(row, idx) in marketListings"
                :key="`${row.kaynak}-${idx}`"
                class="rf-glass rf-interactive rounded-2xl p-4"
              >
                <div class="flex items-start justify-between gap-2">
                  <div>
                    <p class="font-black text-slate-900">{{ row.kaynak || row.provider }}</p>
                    <p class="mt-0.5 text-xs text-slate-500/80">{{ row.benzer_arac || `${row.brand} ${row.model}` }}</p>
                  </div>
                  <p class="shrink-0 text-lg font-black text-emerald-700">
                    {{ formatPrice(row.gunluk_fiyat ?? row.dailyPrice) }}
                  </p>
                </div>
                <p class="mt-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">Günlük</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Maliyet tabanlı fiyat -->
        <PricingCostPanel
          :quote="costAnalysis"
          :loading="finance.quoteLoading"
          :market-average="marketAverage"
          :rental-days="rentalDays"
          @edit-vehicle="openEditModal"
          @offer-accepted="onOfferAccepted"
        />
      </div>
    </template>

    <VehicleFormModal
      v-if="showEditModal && selectedVehicle"
      :edit-vehicle="selectedVehicle"
      :edit-profile="editProfile"
      @close="showEditModal = false"
      @saved="onVehicleSaved"
    />
  </div>
</template>
