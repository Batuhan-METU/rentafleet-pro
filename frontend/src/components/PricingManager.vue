<script setup>
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
const pickupDate = ref('')
const dropoffDate = ref('')
const dateError = ref('')
const analysisReady = ref(false)

const showEditModal = ref(false)
const editProfile = ref(null)
let analysisToken = 0

const priceFormatter = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })

function addDays(base, days) {
  const d = new Date(base)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

const minPickupDate = addDays(new Date(), 1)

function initDates() {
  if (!pickupDate.value) pickupDate.value = addDays(new Date(), 1)
  if (!dropoffDate.value) dropoffDate.value = addDays(new Date(), 4)
}

initDates()

const vehicles = computed(() => store.vehicles)
const loading = computed(() => store.loading)

const dateParams = computed(() => ({
  baslangic: pickupDate.value,
  bitis: dropoffDate.value,
}))

const rentalDays = computed(() => {
  if (!pickupDate.value || !dropoffDate.value) return 0
  const ms = new Date(dropoffDate.value) - new Date(pickupDate.value)
  return Math.max(Math.round(ms / 86400000), 0)
})

const datesValid = computed(() => {
  if (!pickupDate.value || !dropoffDate.value) return false
  if (dropoffDate.value <= pickupDate.value) return false
  if (pickupDate.value < minPickupDate) return false
  return rentalDays.value >= 1
})

const datesReady = computed(() => datesValid.value && analysisReady.value)

const marketSlot = computed(() => {
  const id = selectedVehicleId.value
  if (!id || !datesValid.value) return null
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

const marketStatistics = computed(() => {
  if (!marketSlot.value) return null
  return store.marketStatisticsById[marketSlot.value] ?? null
})

const costAnalysis = computed(() =>
  selectedVehicleId.value ? finance.decisionFor(selectedVehicleId.value) : null,
)

const rentalQuote = computed(() =>
  selectedVehicleId.value ? finance.quoteFor(selectedVehicleId.value) : null,
)

const marketAverage = computed(() => {
  const fromApi = marketStatistics.value?.averagePrice
  if (fromApi != null) return fromApi
  return costAnalysis.value?.piyasa?.gunluk?.ortalama ?? null
})

const windowLabel = computed(() => {
  if (!datesValid.value) return ''
  try {
    const fmt = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' })
    return `${fmt.format(new Date(`${pickupDate.value}T12:00:00`))} → ${fmt.format(new Date(`${dropoffDate.value}T12:00:00`))} (${rentalDays.value} gün)`
  } catch {
    return `${pickupDate.value} → ${dropoffDate.value} (${rentalDays.value} gün)`
  }
})

function formatPrice(value) {
  return value != null ? `${priceFormatter.format(value)} ₺` : '—'
}

function validateDates() {
  dateError.value = ''
  if (!pickupDate.value || !dropoffDate.value) {
    dateError.value = 'Alış ve dönüş tarihlerini seçin.'
    return false
  }
  if (dropoffDate.value <= pickupDate.value) {
    dateError.value = 'Dönüş tarihi alıştan sonra olmalı.'
    return false
  }
  if (pickupDate.value < minPickupDate) {
    dateError.value = 'Alış tarihi en erken yarın.'
    return false
  }
  if (rentalDays.value < 1) {
    dateError.value = 'En az 1 günlük kiralama seçin.'
    return false
  }
  return true
}

async function runAnalysis({ refreshMarket = false } = {}) {
  const vehicleId = selectedVehicleId.value
  if (!vehicleId || !validateDates()) {
    analysisReady.value = false
    return
  }

  const seq = ++analysisToken
  const opts = dateParams.value
  analysisReady.value = false

  const [marketResult, decisionResult] = await Promise.allSettled([
    store.fetchCompetitorPrices(vehicleId, { force: refreshMarket, ...opts }),
    finance.fetchPricingDecision(vehicleId, { force: true, ...opts }),
  ])

  const stillCurrent =
    seq === analysisToken &&
    selectedVehicleId.value === vehicleId &&
    dateParams.value.baslangic === opts.baslangic &&
    dateParams.value.bitis === opts.bitis

  if (!stillCurrent) return

  analysisReady.value =
    decisionResult.status === 'fulfilled' && !!finance.decisionFor(vehicleId)

  if (marketResult.status === 'rejected' && decisionResult.status === 'rejected') {
    analysisReady.value = false
  }
}

let analysisScheduled = false

function scheduleAnalysis(opts = {}) {
  if (analysisScheduled) return
  analysisScheduled = true
  void nextTick(() => {
    analysisScheduled = false
    void runAnalysis(opts)
  })
}

function selectVehicle(id) {
  if (selectedVehicleId.value === id) {
    scheduleAnalysis()
    return
  }
  selectedVehicleId.value = id
}

async function openEditModal() {
  if (!selectedVehicle.value) return
  editProfile.value = await finance.fetchProfile(selectedVehicleId.value)
  showEditModal.value = true
}

async function onVehicleSaved() {
  showEditModal.value = false
  await store.fetchVehicles()
  if (selectedVehicleId.value) await runAnalysis({ refreshMarket: true })
}

async function onSimulationApplied() {
  await store.fetchVehicles()
  await runAnalysis()
}

async function onOfferAccepted(price, dailyRate) {
  if (!selectedVehicle.value || !datesValid.value) return
  workflow.acceptPricingOffer({
    vehicle: selectedVehicle.value,
    agreedPrice: price,
    agreedDailyRate: dailyRate,
    pickupDate: pickupDate.value,
    dropoffDate: dropoffDate.value,
  })
  ui.navigate('drivers', { isFleetManager: auth.isFleetManager })
  await nextTick()
  void driverStore.fetchDrivers()
}

watch(selectedVehicleId, (id) => {
  if (id && workflow.active) {
    const v = vehicles.value.find((x) => x.id === id)
    if (v) workflow.selectVehicle(v)
  }
})

watch(
  [selectedVehicleId, pickupDate, dropoffDate],
  () => {
    if (selectedVehicleId.value && validateDates()) {
      scheduleAnalysis()
    } else {
      analysisReady.value = false
    }
  },
  { immediate: true },
)

watch(
  vehicles,
  (list) => {
    if (workflow.active && workflow.vehicleId) {
      if (selectedVehicleId.value !== workflow.vehicleId) {
        selectedVehicleId.value = workflow.vehicleId
      }
      return
    }
    if (list.length && !selectedVehicleId.value) {
      selectedVehicleId.value = list[0].id
    }
  },
  { immediate: true },
)

onMounted(async () => {
  if (!store.vehicles.length) {
    await store.fetchVehicles()
  }
  if (!selectedVehicleId.value && store.vehicles.length) {
    selectedVehicleId.value = store.vehicles[0].id
  }
})
</script>

<template>
  <div class="mx-auto max-w-7xl space-y-4">
    <RentalWorkflowProgress v-if="readyForDriverPick">
      <p class="mt-2 text-sm text-slate-600">
        Devam eden kiralama var.
        <button type="button" class="font-medium text-brand-600 underline" @click="ui.navigate('drivers', { isFleetManager: auth.isFleetManager })">
          Sürücü seç →
        </button>
      </p>
    </RentalWorkflowProgress>

    <div v-if="loading && !vehicles.length" class="flex justify-center py-16">
      <div class="h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-slate-800" />
    </div>

    <template v-else>
      <!-- 1. Tarih + araç -->
      <div class="rf-glass-strong rounded-3xl p-5">
        <p class="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          <span class="grid h-5 w-5 place-items-center rounded-full bg-brand-600 text-[10px] font-black text-white">1</span>
          Kiralama Dönemi
        </p>
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label class="text-xs font-medium text-slate-500">Alış tarihi</label>
            <input v-model="pickupDate" type="date" :min="minPickupDate" class="rf-input mt-1 w-full" />
          </div>
          <div>
            <label class="text-xs font-medium text-slate-500">Dönüş tarihi</label>
            <input v-model="dropoffDate" type="date" :min="pickupDate || minPickupDate" class="rf-input mt-1 w-full" />
          </div>
          <div class="flex items-end">
            <div class="w-full rounded-2xl bg-brand-50 px-3 py-2.5 text-center">
              <p class="text-xs font-bold uppercase tracking-wide text-brand-700/70">Süre</p>
              <p class="text-lg font-black text-brand-900">{{ datesValid ? rentalDays : '—' }} gün</p>
            </div>
          </div>
          <div class="flex items-end">
            <button
              type="button"
              class="rf-btn-primary w-full justify-center disabled:opacity-40"
              :disabled="!selectedVehicleId || competitorLoading || finance.quoteLoading"
              @click="runAnalysis({ refreshMarket: true })"
            >
              {{ competitorLoading || finance.quoteLoading ? 'Hesaplanıyor…' : 'Yenile' }}
            </button>
          </div>
        </div>
        <p v-if="dateError" class="mt-2 text-sm font-semibold text-red-600">{{ dateError }}</p>
        <p v-else-if="analysisReady && windowLabel" class="mt-2 text-xs text-slate-500">{{ windowLabel }}</p>
      </div>

      <!-- Araç seçimi -->
      <div class="rf-glass-strong rounded-3xl p-5">
        <p class="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          <span class="grid h-5 w-5 place-items-center rounded-full bg-brand-600 text-[10px] font-black text-white">2</span>
          Araç
        </p>
        <div class="flex gap-2 overflow-x-auto pb-1">
          <button
            v-for="v in vehicles"
            :key="v.id"
            type="button"
            class="shrink-0 rounded-2xl border px-3.5 py-2.5 text-left text-sm transition-all duration-200"
            :class="selectedVehicleId === v.id
              ? 'border-transparent bg-gradient-to-br from-brand-600 to-brand-700 text-white shadow-md'
              : 'border-white/50 bg-white/40 text-slate-700 hover:border-brand-300 hover:bg-white/70'"
            @click="selectVehicle(v.id)"
          >
            <span class="font-black tracking-wide">{{ v.plate_number }}</span>
            <span class="block text-xs opacity-80">{{ v.brand }} {{ v.model }}</span>
          </button>
        </div>
      </div>

      <!-- 3. Analiz panelleri -->
      <div v-if="selectedVehicleId && analysisReady" class="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:items-start">
        <!-- Piyasa -->
        <div class="rf-glass-strong flex max-h-[32rem] flex-col overflow-hidden rounded-3xl">
          <div class="border-b border-white/30 px-5 py-4">
            <h3 class="text-sm font-black uppercase tracking-wide text-slate-800">Piyasa Fiyatları</h3>
            <p class="text-xs text-slate-500">{{ windowLabel }}</p>
          </div>
          <div v-if="marketStatistics" class="grid grid-cols-3 gap-2 border-b border-white/30 px-5 py-3 text-center text-xs">
            <div class="rounded-2xl bg-slate-900/[0.03] px-2 py-2.5">
              <p class="font-bold uppercase tracking-wide text-slate-400">Min</p>
              <p class="mt-0.5 font-black text-slate-800">{{ formatPrice(marketStatistics.minPrice) }}</p>
            </div>
            <div class="rounded-2xl bg-brand-50 px-2 py-2.5">
              <p class="font-bold uppercase tracking-wide text-brand-700/70">Ort</p>
              <p class="mt-0.5 font-black text-brand-900">{{ formatPrice(marketStatistics.averagePrice) }}</p>
            </div>
            <div class="rounded-2xl bg-slate-900/[0.03] px-2 py-2.5">
              <p class="font-bold uppercase tracking-wide text-slate-400">Max</p>
              <p class="mt-0.5 font-black text-slate-800">{{ formatPrice(marketStatistics.maxPrice) }}</p>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto">
            <div v-if="competitorLoading && !marketListings.length" class="py-12 text-center text-sm text-slate-400">
              Yükleniyor…
            </div>
            <table v-else-if="marketListings.length" class="w-full text-sm">
              <thead class="sticky top-0 bg-white/90 text-xs font-bold uppercase tracking-wide text-slate-400 backdrop-blur-sm">
                <tr>
                  <th class="px-5 py-2 text-left">Firma</th>
                  <th class="px-5 py-2 text-left">Araç</th>
                  <th class="px-5 py-2 text-right">Günlük</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, idx) in marketListings"
                  :key="idx"
                  class="border-t border-white/30 transition-colors hover:bg-white/40"
                >
                  <td class="px-5 py-2.5 font-semibold text-slate-800">{{ row.kaynak || row.provider }}</td>
                  <td class="px-5 py-2.5 text-slate-500">{{ row.benzer_arac || `${row.brand} ${row.model}` }}</td>
                  <td class="px-5 py-2.5 text-right font-black text-slate-900">
                    {{ formatPrice(row.gunluk_fiyat ?? row.dailyPrice) }}
                  </td>
                </tr>
              </tbody>
            </table>
            <p v-else class="py-12 text-center text-sm text-slate-400">Piyasa verisi yok</p>
          </div>
        </div>

        <!-- Maliyet + fiyat -->
        <div class="max-h-[32rem] lg:max-h-none">
          <PricingCostPanel
            :vehicle-id="selectedVehicleId"
            :decision="costAnalysis"
            :quote="rentalQuote"
            :loading="finance.quoteLoading"
            :offer-loading="finance.offerPreviewLoading"
            :market-average="marketAverage"
            :rental-days="rentalDays"
            :date-baslangic="dateParams.baslangic"
            :date-bitis="dateParams.bitis"
            :dates-ready="datesReady"
            :window-label="windowLabel"
            @edit-vehicle="openEditModal"
            @offer-accepted="onOfferAccepted"
            @simulation-applied="onSimulationApplied"
          />
        </div>
      </div>

      <div
        v-else-if="selectedVehicleId && !analysisReady"
        class="rf-glass rounded-3xl border border-dashed border-white/50 px-4 py-10 text-center text-sm text-slate-500"
      >
        <template v-if="competitorLoading || finance.quoteLoading">
          Piyasa verileri ve maliyet analizi yükleniyor…
        </template>
        <template v-else-if="!datesValid">
          Kiralama tarihlerini seçin.
        </template>
        <template v-else>
          Veriler hazırlanıyor…
        </template>
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
