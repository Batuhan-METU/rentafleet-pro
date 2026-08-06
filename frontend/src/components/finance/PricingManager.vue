<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useVehicleStore } from '../../stores/vehicleStore.js'
import { useVehicleMarketStore } from '../../stores/vehicleMarketStore.js'
import { useFinanceStore } from '../../stores/financeStore.js'
import { useRentalWorkflowStore } from '../../stores/rentalWorkflowStore.js'
import { useDriverStore } from '../../stores/driverStore.js'
import { useUiStore } from '../../stores/uiStore.js'
import { useAuthStore } from '../../stores/authStore.js'
import PricingCostPanel from './PricingCostPanel.vue'
import VehicleFormModal from '../VehicleFormModal.vue'
import RentalWorkflowProgress from '../RentalWorkflowProgress.vue'
import DatePicker from '../vehicle-form/DatePicker.vue'
import TimePicker from '../vehicle-form/TimePicker.vue'
import { getDefaultRentalWindow } from '../../utils/defaultRentalWindow.js'

const store = useVehicleStore()
const marketStore = useVehicleMarketStore()
const finance = useFinanceStore()
const workflow = useRentalWorkflowStore()
const { readyForDriverPick } = storeToRefs(workflow)
const driverStore = useDriverStore()
const ui = useUiStore()
const auth = useAuthStore()

const selectedVehicleId = ref(null)
const vehicleSearch = ref('')
const showVehicleDropdown = ref(false)
const pickupDate = ref('')
const dropoffDate = ref('')
const pickupTime = ref('10:00')
const dropoffTime = ref('10:00')
const dateError = ref('')
const analysisReady = ref(false)

const showEditModal = ref(false)
const editProfile = ref(null)
const editRegistrationDetail = ref(null)
let analysisToken = 0

const priceFormatter = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })

const defaultWindow = getDefaultRentalWindow()
const minPickupDate = defaultWindow.pickupDate

function initDates() {
  if (!pickupDate.value) pickupDate.value = defaultWindow.pickupDate
  if (!dropoffDate.value) dropoffDate.value = defaultWindow.dropoffDate
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
  return marketStore.marketSlotKey(id, dateParams.value.baslangic, dateParams.value.bitis)
})

const competitorLoading = computed(
  () => marketSlot.value && marketStore.competitorLoadingId === marketSlot.value,
)

const selectedVehicle = computed(() =>
  vehicles.value.find((v) => v.id === selectedVehicleId.value) ?? null,
)

// İki BAĞIMSIZ eşleşme yöntemi — SIPP (uluslararası kod segmenti) ve TSB
// Tip Kodu (TSB kataloğunda birebir aynı model). Biri diğerinin yedeği
// değil; ikisi de ayrı bölüm olarak gösterilir (bkz. şablon).
const sippMatch = computed(() => (marketSlot.value ? marketStore.sippMatchById[marketSlot.value] ?? null : null))
const tsbMatch = computed(() => (marketSlot.value ? marketStore.tsbMatchById[marketSlot.value] ?? null : null))

const marketBlocks = computed(() => [
  { title: 'SIPP Eşleşmeleri', match: sippMatch.value },
  { title: 'TSB Tip Kodu Eşleşmeleri', match: tsbMatch.value },
])

const costAnalysis = computed(() =>
  selectedVehicleId.value ? finance.decisionFor(selectedVehicleId.value) : null,
)

const rentalQuote = computed(() =>
  selectedVehicleId.value ? finance.quoteFor(selectedVehicleId.value) : null,
)

// Fiyat önerisi motoruna giden tek sayı: TSB Tip Kodu eşleşmesi (birebir
// katalog eşleşmesi olduğu için daha güvenilir) birincil kaynak; SIPP
// bloğu yalnızca referans/karşılaştırma amaçlı gösterilir.
const marketAverage = computed(() => {
  const fromTsb = tsbMatch.value?.statistics?.averagePrice
  if (fromTsb != null) return fromTsb
  return costAnalysis.value?.market?.daily?.avg ?? null
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
    marketStore.fetchCompetitorPrices(vehicleId, { force: refreshMarket, ...opts }),
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

// Araç arama: plaka, marka veya modele göre filtreler. Sorgu boşsa (ör.
// aşağı ok tuşuna basılınca) filodaki TÜM araçlar listelenir — kullanıcı
// hiç yazmadan da listeden gözle seçim yapabilsin diye.
const normalizedVehicleSearch = computed(() => vehicleSearch.value.trim().toLocaleLowerCase('tr'))

const filteredVehicleOptions = computed(() => {
  const q = normalizedVehicleSearch.value
  if (!q) return vehicles.value
  return vehicles.value.filter((v) =>
    `${v.plate_number} ${v.brand} ${v.model}`.toLocaleLowerCase('tr').includes(q),
  )
})

const vehicleSearchInput = ref(null)

function toggleVehicleDropdown() {
  showVehicleDropdown.value = !showVehicleDropdown.value
  if (showVehicleDropdown.value) vehicleSearchInput.value?.focus()
}

// Satıra (input'a) tıklayınca aç/kapa: mousedown, tarayıcının native
// odak-değiştirmesinden ÖNCE fırlar — input hâlâ odaksızsa hiçbir şey
// yapmadan native `@focus` handler'ının açmasına izin verilir (ilk
// tıklama = aç); input ZATEN odaktaysa (liste zaten açık) burada
// elle kapatılır (ikinci tıklama = kapa) — çünkü aynı elemana tekrar
// tıklamak yeni bir focus olayı DOĞURMAZ, @focus tek başına bunu
// yakalayamaz.
function handleSearchRowMousedown() {
  if (document.activeElement === vehicleSearchInput.value) {
    showVehicleDropdown.value = !showVehicleDropdown.value
  }
}

// Inline şablon ifadelerinde çıplak `setTimeout` global'e değil `_ctx`'e
// (bileşen örneğine) çözümlenir ve "setTimeout is not a function" hatası
// verir — bu yüzden gecikmeli kapatma burada, script bağlamında yapılır.
// Kapatmadan hemen önce input'un hâlâ odakta olmadığı kontrol edilir:
// örn. seçili araç rozetine tıklamak önce input'u blur'lar (tarayıcının
// doğal odak-değiştirme davranışı) SONRA toggleVehicleDropdown senkron
// olarak input'u yeniden odaklar — bu kontrol olmadan, blur'un 150ms
// sonraki zamanlayıcısı yeniden açılmış listeyi hemen kapatırdı.
function closeVehicleDropdownDelayed() {
  window.setTimeout(() => {
    if (document.activeElement !== vehicleSearchInput.value) {
      showVehicleDropdown.value = false
    }
  }, 150)
}

function pickVehicle(v) {
  selectVehicle(v.id)
  vehicleSearch.value = ''
  showVehicleDropdown.value = false
}

function normalizePlate(plate) {
  return (plate || '').toLocaleLowerCase('tr').replace(/\s+/g, '')
}

watch(vehicleSearch, (raw) => {
  const q = normalizePlate(raw)
  if (!q) return
  const exactPlateMatch = vehicles.value.find((v) => normalizePlate(v.plate_number) === q)
  if (exactPlateMatch) pickVehicle(exactPlateMatch)
})

async function openEditModal() {
  if (!selectedVehicle.value) return
  const [profile, registrationDetail] = await Promise.all([
    finance.fetchProfile(selectedVehicleId.value),
    finance.fetchRegistrationDetail(selectedVehicleId.value),
  ])
  editProfile.value = profile
  editRegistrationDetail.value = registrationDetail
  showEditModal.value = true
}

async function onVehicleSaved() {
  showEditModal.value = false
  await store.fetchVehicles()
  if (selectedVehicleId.value) await runAnalysis({ refreshMarket: true })
}

async function onOfferAccepted(price, dailyRate) {
  if (!selectedVehicle.value || !datesValid.value) return
  workflow.acceptPricingOffer({
    vehicle: selectedVehicle.value,
    agreedPrice: price,
    agreedDailyRate: dailyRate,
    pickupDate: pickupDate.value,
    dropoffDate: dropoffDate.value,
    pickupTime: pickupTime.value,
    dropoffTime: dropoffTime.value,
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

// Sayfa normalde boş açılır — araç yalnızca kullanıcı arayıp seçtiğinde
// (veya başka bir sayfadan devam eden bir kiralama akışı taşındığında)
// belirlenir. İlk aracı otomatik seçmiyoruz.
watch(
  vehicles,
  (list) => {
    if (workflow.active && workflow.vehicleId && selectedVehicleId.value !== workflow.vehicleId) {
      if (list.some((v) => v.id === workflow.vehicleId)) {
        selectedVehicleId.value = workflow.vehicleId
      }
    }
  },
  { immediate: true },
)

onMounted(async () => {
  if (!store.vehicles.length) {
    await store.fetchVehicles()
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
        <div class="grid gap-3 sm:grid-cols-4">
          <div>
            <label class="text-xs font-medium text-slate-500">Alış tarihi</label>
            <div class="mt-1">
              <DatePicker v-model="pickupDate" />
            </div>
          </div>
          <div>
            <label class="text-xs font-medium text-slate-500">Alış saati</label>
            <div class="mt-1">
              <TimePicker v-model="pickupTime" />
            </div>
          </div>
          <div>
            <label class="text-xs font-medium text-slate-500">Dönüş tarihi</label>
            <div class="mt-1">
              <DatePicker v-model="dropoffDate" />
            </div>
          </div>
          <div>
            <label class="text-xs font-medium text-slate-500">Dönüş saati</label>
            <div class="mt-1">
              <TimePicker v-model="dropoffTime" />
            </div>
          </div>
        </div>
        <div class="mt-3 inline-flex rounded-2xl bg-brand-50 px-4 py-2.5 text-center">
          <p class="text-xs font-bold uppercase tracking-wide text-brand-700/70">Süre:&nbsp;</p>
          <p class="text-xs font-black text-brand-900">{{ datesValid ? rentalDays : '—' }} gün</p>
        </div>
        <p v-if="dateError" class="mt-2 text-sm font-semibold text-red-600">{{ dateError }}</p>
        <p v-else-if="analysisReady && windowLabel" class="mt-2 text-xs text-slate-500">{{ windowLabel }}</p>
      </div>

      <!-- Araç seçimi: plaka/marka/model arama -->
      <div class="relative z-20 rf-glass-strong rounded-3xl p-5">
        <p class="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
          <span class="grid h-5 w-5 place-items-center rounded-full bg-brand-600 text-[10px] font-black text-white">2</span>
          Araç
        </p>
        <div class="relative">
          <input
            ref="vehicleSearchInput"
            v-model="vehicleSearch"
            type="search"
            placeholder="Plaka, marka veya model ara..."
            class="rf-input w-full !border-transparent !bg-brand-50/60 !pr-10 placeholder:text-slate-400"
            @mousedown="handleSearchRowMousedown"
            @focus="showVehicleDropdown = true"
            @blur="closeVehicleDropdownDelayed"
          />
          <button
            type="button"
            class="absolute right-2 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Araç listesini göster"
            @mousedown.prevent.stop="toggleVehicleDropdown"
          >
            <svg class="h-4 w-4 transition-transform" :class="{ 'rotate-180': showVehicleDropdown }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          <div
            v-if="showVehicleDropdown && filteredVehicleOptions.length"
            class="absolute z-10 mt-2 max-h-72 w-full overflow-y-auto rounded-2xl border border-slate-100 bg-white shadow-xl"
          >
            <button
              v-for="v in filteredVehicleOptions"
              :key="v.id"
              type="button"
              class="flex w-full cursor-pointer items-center justify-between gap-2 px-4 py-2.5 text-left text-sm transition-colors hover:bg-brand-50"
              @mousedown.prevent="pickVehicle(v)"
            >
              <span class="font-black tracking-wide text-slate-900">{{ v.plate_number }}</span>
              <span class="text-slate-500">{{ v.brand }} {{ v.model }}</span>
            </button>
          </div>
          <div
            v-else-if="showVehicleDropdown && vehicleSearch"
            class="absolute z-10 mt-2 w-full rounded-2xl border border-slate-100 bg-white px-4 py-3 text-sm text-slate-400 shadow-xl"
          >
            Eşleşen araç bulunamadı.
          </div>
        </div>

        <button
          v-if="selectedVehicle"
          type="button"
          class="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-2xl bg-slate-900/[0.03] px-3.5 py-2 text-left hover:bg-slate-900/[0.06]"
          @click="toggleVehicleDropdown"
        >
          <span class="font-black tracking-wide text-slate-900">{{ selectedVehicle.plate_number }}</span>
          <span class="text-sm text-slate-500">{{ selectedVehicle.brand }} {{ selectedVehicle.model }}</span>
        </button>
      </div>

      <!-- 3. Analiz panelleri -->
      <div v-if="selectedVehicleId && analysisReady" class="grid grid-cols-1 gap-4 lg:grid-cols-2 lg:items-start">
        <!-- Piyasa: iki BAĞIMSIZ eşleşme yöntemi ayrı bölümler halinde -->
        <div class="rf-glass-strong flex max-h-[32rem] flex-col overflow-hidden rounded-3xl">
          <div class="border-b border-white/30 px-5 py-4">
            <h3 class="text-sm font-black uppercase tracking-wide text-slate-800">Piyasa Fiyatları</h3>
            <p class="text-xs text-slate-500">{{ windowLabel }}</p>
          </div>
          <div class="flex-1 divide-y divide-white/30 overflow-y-auto">
            <section v-for="block in marketBlocks" :key="block.title" class="px-5 py-4">
              <h4 class="mb-0.5 text-xs font-black uppercase tracking-wide text-brand-700">{{ block.title }}</h4>
              <p v-if="block.match?.matchedSegment" class="mb-3 text-[11px] text-slate-400">{{ block.match.matchedSegment }}</p>

              <div v-if="block.match?.statistics" class="mb-3 grid grid-cols-3 gap-2 text-center text-xs">
                <div class="rounded-2xl bg-slate-900/[0.03] px-2 py-2.5">
                  <p class="font-bold uppercase tracking-wide text-slate-400">Min</p>
                  <p class="mt-0.5 font-black text-slate-800">{{ formatPrice(block.match.statistics.minPrice) }}</p>
                </div>
                <div class="rounded-2xl bg-brand-50 px-2 py-2.5">
                  <p class="font-bold uppercase tracking-wide text-brand-700/70">Ort</p>
                  <p class="mt-0.5 font-black text-brand-900">{{ formatPrice(block.match.statistics.averagePrice) }}</p>
                </div>
                <div class="rounded-2xl bg-slate-900/[0.03] px-2 py-2.5">
                  <p class="font-bold uppercase tracking-wide text-slate-400">Max</p>
                  <p class="mt-0.5 font-black text-slate-800">{{ formatPrice(block.match.statistics.maxPrice) }}</p>
                </div>
              </div>

              <div v-if="competitorLoading && !block.match?.matchedVehicles?.length" class="py-6 text-center text-sm text-slate-400">
                Yükleniyor…
              </div>
              <table v-else-if="block.match?.matchedVehicles?.length" class="w-full text-sm">
                <thead class="text-xs font-bold uppercase tracking-wide text-slate-400">
                  <tr>
                    <th class="py-2 pr-2 text-left">Firma</th>
                    <th class="py-2 pr-2 text-left">Araç</th>
                    <th class="py-2 text-right">Günlük</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, idx) in block.match.matchedVehicles"
                    :key="idx"
                    class="border-t border-slate-100 transition-colors hover:bg-white/40"
                  >
                    <td class="py-2 pr-2 font-semibold text-slate-800">{{ row.provider }}</td>
                    <td class="py-2 pr-2 text-slate-500">{{ row.brand }} {{ row.model }}</td>
                    <td class="py-2 text-right font-black text-slate-900">{{ formatPrice(row.dailyPrice) }}</td>
                  </tr>
                </tbody>
              </table>
              <p v-else class="py-6 text-center text-sm text-slate-400">Piyasa verisi yok</p>
            </section>
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
            @edit-vehicle="openEditModal"
            @offer-accepted="onOfferAccepted"
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
      :edit-registration-detail="editRegistrationDetail"
      @close="showEditModal = false"
      @saved="onVehicleSaved"
    />
  </div>
</template>
