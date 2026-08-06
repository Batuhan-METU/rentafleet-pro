<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRentalStore } from '../stores/rentalStore.js'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'
import { useVehicleStore } from '../stores/vehicleStore.js'
import { useDriverStore } from '../stores/driverStore.js'
import { useUiStore } from '../stores/uiStore.js'
import { useAuthStore } from '../stores/authStore.js'
import RentalWorkflowProgress from './RentalWorkflowProgress.vue'
import maleIcon from './icons/3233508.png'
import femaleIcon from './icons/3577099.png'
import ReturnVehicleModal from './ReturnVehicleModal.vue'
import ExtendRentalModal from './ExtendRentalModal.vue'
import CancelRentalModal from './CancelRentalModal.vue'
import DatePicker from './vehicle-form/DatePicker.vue'
import TimePicker from './vehicle-form/TimePicker.vue'
import { formatTL, formatDate } from '../utils/format.js'
import { downloadExcelReport } from '../utils/exportExcel.js'
import { getApiErrorMessage } from '../utils/apiError.js'

const rentalStore = useRentalStore()
const workflow = useRentalWorkflowStore()
const { readyForDriverPick } = storeToRefs(workflow)
const vehicleStore = useVehicleStore()
const driverStore = useDriverStore()
const ui = useUiStore()
const auth = useAuthStore()

const listTab = ref('ACTIVE')
const historyFilter = ref('TUMU')
const formError = ref('')
const successMessage = ref('')

const tabs = [
  { id: 'ACTIVE', label: 'Aktif', countKey: 'active' },
  { id: 'UPCOMING', label: 'Gelecek', countKey: 'upcoming' },
  { id: 'PAST', label: 'Geçmiş Kiralamalar', countKey: 'past' },
]

function tabCount(tab) {
  return rentalStore.summary[tab.countKey] ?? 0
}

// "Geçmiş Kiralamalar" seçiliyken gösterilen alt kategori: hepsi ya da
// zamanında / erken teslim alınan / geç teslim alınan üçlü ayrımı.
const historyFilters = [
  { id: 'TUMU', label: 'Tümü' },
  { id: 'ON_TIME', label: 'Zamanında' },
  { id: 'EARLY', label: 'Erken Teslim Alınan' },
  { id: 'LATE', label: 'Geç Teslim Alınan' },
]

function historyFilterCount(filter) {
  if (filter.id === 'ON_TIME') return rentalStore.summary.past_on_time ?? 0
  if (filter.id === 'EARLY') return rentalStore.summary.past_early ?? 0
  if (filter.id === 'LATE') return rentalStore.summary.past_late ?? 0
  return rentalStore.summary.past ?? 0
}

// Geçmiş sekmesi sunucu tarafında sayfalanır — sekme veya alt-filtre
// değiştiğinde 1. sayfadan yeniden çekilir, sayfa geçişinde de aynı istek
// (yalnızca `page` değişir) tekrar tetiklenir. Hiçbir zaman tüm geçmiş tek
// seferde çekilmez.
watch(listTab, (v) => {
  if (v !== 'PAST') {
    historyFilter.value = 'TUMU'
  } else {
    rentalStore.fetchPastRentals({ page: 1, returnTiming: historyFilter.value })
  }
})

watch(historyFilter, (v) => {
  if (listTab.value === 'PAST') {
    rentalStore.fetchPastRentals({ page: 1, returnTiming: v })
  }
})

function goToPastPage(page) {
  if (page < 1 || page > rentalStore.pastTotalPages || page === rentalStore.pastPage) return
  rentalStore.fetchPastRentals({ page, returnTiming: historyFilter.value })
}

const listedRentals = computed(() => {
  if (listTab.value === 'ACTIVE') return rentalStore.activeRentals
  if (listTab.value === 'UPCOMING') return rentalStore.upcomingRentals
  // PAST: backend zaten sayfalayıp/filtreleyip döndürüyor, istemci tarafında
  // ek bir filtre uygulanmaz.
  return rentalStore.pastRentals
})

function parsePrice(raw) {
  if (!raw) return null
  const n = Number(String(raw).replace(/\s/g, '').replace(/\./g, '').replace(',', '.'))
  return Number.isNaN(n) || n <= 0 ? null : n
}

function daysBetween(pickup, dropoff) {
  if (!pickup || !dropoff) return null
  const diff = (new Date(dropoff) - new Date(pickup)) / (1000 * 60 * 60 * 24)
  return diff > 0 ? Math.round(diff) : null
}

const workflowForm = ref({
  pickupDate: '',
  dropoffDate: '',
  pickupTime: '10:00',
  dropoffTime: '10:00',
  dailyRate: '',
})

const workflowFormTotal = computed(() => {
  const rate = parsePrice(workflowForm.value.dailyRate)
  const days = daysBetween(workflowForm.value.pickupDate, workflowForm.value.dropoffDate)
  return rate && days ? rate * days : null
})

watch(
  () => workflow.pickupDate,
  (v) => {
    if (v) workflowForm.value.pickupDate = v
  },
  { immediate: true },
)

watch(
  () => workflow.dropoffDate,
  (v) => {
    if (v) workflowForm.value.dropoffDate = v
  },
  { immediate: true },
)

watch(
  () => workflow.pickupTime,
  (v) => {
    if (v) workflowForm.value.pickupTime = v
  },
  { immediate: true },
)

watch(
  () => workflow.dropoffTime,
  (v) => {
    if (v) workflowForm.value.dropoffTime = v
  },
  { immediate: true },
)

watch(
  () => workflow.agreedDailyRate,
  (v) => {
    if (v != null) workflowForm.value.dailyRate = String(v)
  },
  { immediate: true },
)

async function createRental(payload, { clearWorkflow = false } = {}) {
  formError.value = ''
  successMessage.value = ''

  if (!payload.driver_id || !payload.vehicle_id) {
    formError.value = 'Sürücü ve araç seçilmelidir.'
    return false
  }
  if (!payload.pickup_date || !payload.dropoff_date) {
    formError.value = 'Alış ve bırakış tarihlerini girin.'
    return false
  }
  if (payload.dropoff_date <= payload.pickup_date) {
    formError.value = 'Bırakış tarihi alış tarihinden sonra olmalıdır.'
    return false
  }

  try {
    await rentalStore.createRental({
      driver_id: Number(payload.driver_id),
      vehicle_id: Number(payload.vehicle_id),
      pickup_date: payload.pickup_date,
      dropoff_date: payload.dropoff_date,
      pickup_time: payload.pickup_time,
      dropoff_time: payload.dropoff_time,
      daily_rate: payload.daily_rate ?? null,
      deposit_amount: payload.deposit_amount ?? null,
    })
    successMessage.value = 'Kiralama oluşturuldu. Araç sürücüye atandı.'
    if (clearWorkflow) workflow.clear()
    await vehicleStore.fetchVehicles()
    await driverStore.fetchDrivers()
    await rentalStore.fetchRentals()
    return true
  } catch (err) {
    formError.value = getApiErrorMessage(err, 'Kiralama oluşturulamadı.')
    return false
  }
}

async function submitWorkflowRental() {
  await createRental({
    driver_id: workflow.driverId,
    vehicle_id: workflow.vehicleId,
    pickup_date: workflowForm.value.pickupDate,
    dropoff_date: workflowForm.value.dropoffDate,
    pickup_time: workflowForm.value.pickupTime,
    dropoff_time: workflowForm.value.dropoffTime,
    daily_rate: parsePrice(workflowForm.value.dailyRate) ?? workflow.agreedDailyRate,
    deposit_amount: workflow.depositAmount,
  }, { clearWorkflow: true })
}

// --- Toplu Excel dışa aktarma ------------------------------------------
// Seçili sekme (Aktif/Gelecek/Geçmiş) ve geçmiş alt-filtresi backend'e
// aynen iletilir: Excel her zaman ekranda listelenen kümeyi indirir.
const exportingExcel = ref(false)
const exportError = ref('')
let exportErrorTimer = null

async function exportRentalsExcel() {
  if (exportingExcel.value) return
  exportingExcel.value = true
  exportError.value = ''
  try {
    const params = { period: listTab.value }
    if (listTab.value === 'PAST' && historyFilter.value !== 'TUMU') {
      params.return_timing = historyFilter.value
    }
    await downloadExcelReport('rentals/export/', {
      params,
      filenamePrefix: 'Kiralama_Raporu',
    })
  } catch {
    exportError.value = 'Excel raporu indirilemedi.'
    clearTimeout(exportErrorTimer)
    exportErrorTimer = setTimeout(() => {
      exportError.value = ''
    }, 4000)
  } finally {
    exportingExcel.value = false
  }
}

const cancelTarget = ref(null)

function openCancelModal(rental) {
  cancelTarget.value = rental
}

function closeCancelModal() {
  cancelTarget.value = null
}

async function onRentalCancelled() {
  successMessage.value = 'Kiralama iptal edildi.'
  await vehicleStore.fetchVehicles()
  await driverStore.fetchDrivers()
}

function canCancelRental(rental) {
  // Aktif kiralamalarda ayrı bir İptal yok — "Teslim Al" zaten erken teslim
  // anlamına gelir. Yalnızca henüz başlamamış (Gelecek) kiralamalar iptal edilir.
  return rental.period_code === 'UPCOMING'
}

function canReturnRental(rental) {
  // period_code'a değil ham status'a bakılır: sözleşme bitiş saati geçmiş
  // ama henüz kapatılmamış (geç teslimat) kiralamalar "Geçmiş" sekmesinde
  // görünür ama backend'de hâlâ ACTIVE'tir — Teslim Al/Uzat orada da çıkmalı.
  // Ama henüz BAŞLAMAMIŞ (Gelecek) bir kiralama — status yine ACTIVE'tir —
  // teslim alınamaz veya uzatılamaz; bu yüzden started_at de kontrol edilir.
  return rental.status === 'ACTIVE' && new Date(rental.started_at) <= new Date()
}

const returnTarget = ref(null)

function openReturnModal(rental) {
  returnTarget.value = rental
}

function closeReturnModal() {
  returnTarget.value = null
}

async function onVehicleReturned() {
  successMessage.value = 'Araç teslim alındı.'
  await vehicleStore.fetchVehicles()
  await driverStore.fetchDrivers()
  await rentalStore.fetchRentals()
}

const extendTarget = ref(null)

function openExtendModal(rental) {
  extendTarget.value = rental
}

function closeExtendModal() {
  extendTarget.value = null
}

async function onRentalExtended() {
  successMessage.value = 'Kiralama uzatıldı.'
  await rentalStore.fetchRentals()
}

function periodBadgeClass(code) {
  if (code === 'ACTIVE') return 'bg-emerald-100 text-emerald-700'
  if (code === 'UPCOMING') return 'bg-sky-100 text-sky-700'
  return 'bg-slate-100 text-slate-600'
}

function avatarIconFor(gender) {
  return gender === 'FEMALE' ? femaleIcon : maleIcon
}

function priceDiffClass(rental) {
  const diff = Number(rental.price_difference)
  if (!diff) return 'text-slate-400'
  return diff < 0 ? 'text-emerald-600' : 'text-rose-600'
}

function formatPriceDiff(rental) {
  if (rental.price_difference == null) return '—'
  const diff = Number(rental.price_difference)
  if (diff === 0) return '₺0'
  const sign = diff < 0 ? '−' : '+'
  return `${sign}${formatTL(Math.abs(diff), { decimals: true })}`
}

onMounted(async () => {
  if (!vehicleStore.vehicles.length) await vehicleStore.fetchVehicles()
  if (!driverStore.drivers.length) await driverStore.fetchDrivers()
  await rentalStore.fetchRentals()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Devam eden kiralama süreci -->
    <RentalWorkflowProgress v-if="readyForDriverPick && !workflow.driverId">
      <p class="mt-2 text-sm text-slate-600">
        Fiyatlandırma tamamlandı. Sürücü seçmek için
        <button type="button" class="font-bold text-brand-600 underline" @click="ui.navigate('drivers', { isFleetManager: auth.isFleetManager })">
          Sürücüler
        </button>
        sayfasına gidin.
      </p>
    </RentalWorkflowProgress>

    <!-- Süreçten gelen hızlı kiralama -->
    <RentalWorkflowProgress v-if="workflow.active && workflow.step === 'rental'">
      <dl class="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt class="text-slate-500">Sürücü</dt>
          <dd class="font-semibold text-slate-800">{{ workflow.driverName }}</dd>
        </div>
        <div>
          <dt class="text-slate-500">Araç</dt>
          <dd class="font-semibold text-slate-800">{{ workflow.vehicleLabel }}</dd>
        </div>
        <div v-if="workflow.agreedPrice != null">
          <dt class="text-slate-500">Anlaşılan fiyat</dt>
          <dd class="font-semibold text-slate-800">{{ formatTL(workflow.agreedPrice, { decimals: true }) }}</dd>
        </div>
      </dl>
    </RentalWorkflowProgress>

    <div
      v-if="workflow.driverId && workflow.vehicleId"
      class="rf-glass-strong rounded-3xl p-6"
    >
      <h3 class="text-lg font-black text-slate-900">Süreçten Gelen Kiralama</h3>
      <p class="mt-1 text-sm text-slate-500">
        {{ workflow.driverName }} → {{ workflow.vehicleLabel }}
      </p>

      <div v-if="formError" class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {{ formError }}
      </div>
      <div v-if="successMessage" class="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
        {{ successMessage }}
      </div>

      <div class="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <label class="text-xs font-medium text-slate-500">Alış Tarihi</label>
          <div class="mt-1"><DatePicker v-model="workflowForm.pickupDate" /></div>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-500">Alış Saati</label>
          <div class="mt-1"><TimePicker v-model="workflowForm.pickupTime" /></div>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-500">Bırakış Tarihi</label>
          <div class="mt-1"><DatePicker v-model="workflowForm.dropoffDate" /></div>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-500">Bırakış Saati</label>
          <div class="mt-1"><TimePicker v-model="workflowForm.dropoffTime" /></div>
        </div>
        <div>
          <label class="text-xs font-medium text-slate-500">Günlük Fiyat (₺)</label>
          <input v-model="workflowForm.dailyRate" type="text" class="rf-input mt-1" />
          <p v-if="workflowFormTotal != null" class="mt-1 text-xs text-slate-500">
            = {{ formatTL(workflowFormTotal, { decimals: true }) }} toplam
          </p>
        </div>
      </div>

      <button
        type="button"
        class="rf-btn-primary mt-5"
        :disabled="rentalStore.creating"
        @click="submitWorkflowRental"
      >
        {{ rentalStore.creating ? 'Oluşturuluyor…' : 'Kiralamayı Onayla ve Aracı Ata' }}
      </button>
    </div>

    <!-- Liste: aktif / gelecek / geçmiş -->
    <div class="rf-glass-strong rounded-3xl p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h3 class="text-lg font-black text-slate-900">Kiralama Kayıtları</h3>
        <div class="flex items-center gap-3">
          <span v-if="exportError" class="text-xs font-semibold text-rose-600">
            {{ exportError }}
          </span>
          <button
            type="button"
            class="rf-btn-secondary !px-4 !py-2 !text-xs"
            :disabled="exportingExcel || rentalStore.loading || !listedRentals.length"
            :title="listedRentals.length ? 'Listelenen kiralamaları Excel olarak indir' : 'İndirilecek kiralama yok'"
            @click="exportRentalsExcel"
          >
            <span
              v-if="exportingExcel"
              class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600"
            ></span>
            <svg v-else class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
            </svg>
            {{ exportingExcel ? 'Hazırlanıyor...' : "Excel'e Aktar" }}
          </button>
        </div>
      </div>

      <div class="mt-4 flex flex-wrap gap-2">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          class="rf-pill-filter"
          :class="listTab === tab.id ? 'rf-pill-filter--active' : 'rf-pill-filter--idle'"
          @click="listTab = tab.id"
        >
          {{ tab.label }}
          <span class="ml-1 opacity-70">({{ tabCount(tab) }})</span>
        </button>
      </div>

      <!-- Geçmiş Kiralamalar seçiliyken: zamanında / erken / geç alt-filtresi -->
      <div v-if="listTab === 'PAST'" class="mt-3 flex flex-wrap items-center gap-2 border-l-2 border-slate-200 pl-3">
        <button
          v-for="filter in historyFilters"
          :key="filter.id"
          type="button"
          class="rf-pill-filter !px-3 !py-1.5 !text-xs"
          :class="historyFilter === filter.id ? 'rf-pill-filter--active' : 'rf-pill-filter--idle'"
          @click="historyFilter = filter.id"
        >
          {{ filter.label }}
          <span class="ml-1 opacity-70">({{ historyFilterCount(filter) }})</span>
        </button>
      </div>

      <div v-if="rentalStore.loading" class="grid place-items-center py-12">
        <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600" />
      </div>
      <p v-else-if="rentalStore.error" class="py-8 text-center text-red-600">Liste yüklenemedi.</p>
      <div v-else-if="listedRentals.length" class="mt-4 overflow-x-auto">
        <table class="w-full min-w-[720px] text-left text-sm">
          <thead>
            <tr class="border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
              <th class="pb-3 pr-4">Sürücü</th>
              <th class="pb-3 pr-4">Araç</th>
              <th class="pb-3 pr-4">Alış</th>
              <th class="pb-3 pr-4">Bırakış</th>
              <th class="pb-3 pr-4">Dönem</th>
              <th class="pb-3 pr-4">Fiyat</th>
              <th v-if="listTab === 'PAST'" class="pb-3 pr-4">Fark</th>
              <th v-if="listTab !== 'PAST'" class="pb-3">İşlem</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in listedRentals"
              :key="r.id"
              class="border-b border-slate-100 transition-colors duration-150 hover:bg-slate-50/80"
            >
              <td class="py-3 pr-4">
                <div class="flex items-center gap-2.5">
                  <span class="grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-full bg-brand-50">
                    <img :src="avatarIconFor(r.driver_gender)" alt="" class="h-6 w-6 object-contain" />
                  </span>
                  <span class="font-semibold text-slate-800">{{ r.driver_name }}</span>
                </div>
              </td>
              <td class="py-3 pr-4">
                <span class="font-bold">{{ r.plate_number }}</span>
                <span class="ml-1 text-slate-500">{{ r.brand_model }}</span>
              </td>
              <td class="py-3 pr-4 text-slate-600">{{ formatDate(r.started_at) }}</td>
              <td class="py-3 pr-4 text-slate-600">{{ formatDate(r.ended_at) }}</td>
              <td class="py-3 pr-4">
                <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="periodBadgeClass(r.period_code)">
                  {{ r.period_label }}
                </span>
              </td>
              <td class="py-3 pr-4 font-semibold text-slate-800">
                {{ r.quoted_total ? formatTL(r.quoted_total, { decimals: true }) : '—' }}
              </td>
              <td v-if="listTab === 'PAST'" class="py-3 pr-4 font-semibold" :class="priceDiffClass(r)">
                {{ formatPriceDiff(r) }}
              </td>
              <td v-if="listTab !== 'PAST'" class="py-3">
                <div class="flex flex-wrap items-center gap-2">
                  <button
                    v-if="canReturnRental(r)"
                    type="button"
                    class="cursor-pointer rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-xs font-bold text-emerald-700 transition-colors hover:bg-emerald-100"
                    @click="openReturnModal(r)"
                  >
                    Teslim Al
                  </button>
                  <button
                    v-if="canReturnRental(r)"
                    type="button"
                    class="cursor-pointer rounded-lg border border-sky-200 bg-sky-50 px-2.5 py-1.5 text-xs font-bold text-sky-700 transition-colors hover:bg-sky-100"
                    @click="openExtendModal(r)"
                  >
                    Uzat
                  </button>
                  <button
                    v-if="canCancelRental(r)"
                    type="button"
                    class="cursor-pointer rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1.5 text-xs font-bold text-rose-700 transition-colors hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="rentalStore.cancellingId === r.id"
                    @click="openCancelModal(r)"
                  >
                    {{ rentalStore.cancellingId === r.id ? 'İptal…' : 'Kiralamayı İptal' }}
                  </button>
                  <span v-if="!canReturnRental(r) && !canCancelRental(r)" class="text-xs text-slate-400">—</span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <div
          v-if="listTab === 'PAST' && rentalStore.pastTotalPages > 1"
          class="mt-4 flex items-center justify-center gap-3"
        >
          <button
            type="button"
            class="rf-btn-secondary !px-4 !py-2 !text-xs disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="rentalStore.pastPage <= 1 || rentalStore.pastLoading"
            @click="goToPastPage(rentalStore.pastPage - 1)"
          >
            ‹ Önceki
          </button>
          <span class="text-xs font-semibold text-slate-500">
            Sayfa {{ rentalStore.pastPage }} / {{ rentalStore.pastTotalPages }}
          </span>
          <button
            type="button"
            class="rf-btn-secondary !px-4 !py-2 !text-xs disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="rentalStore.pastPage >= rentalStore.pastTotalPages || rentalStore.pastLoading"
            @click="goToPastPage(rentalStore.pastPage + 1)"
          >
            Sonraki ›
          </button>
        </div>
      </div>
      <div v-else-if="listTab === 'PAST' && rentalStore.pastLoading" class="grid place-items-center py-12">
        <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600" />
      </div>
      <p v-else class="py-10 text-center text-slate-500">
        Bu kategoride kiralama yok.
      </p>
    </div>

    <ReturnVehicleModal
      v-if="returnTarget"
      :rental="returnTarget"
      @close="closeReturnModal"
      @returned="onVehicleReturned"
    />

    <ExtendRentalModal
      v-if="extendTarget"
      :rental="extendTarget"
      @close="closeExtendModal"
      @extended="onRentalExtended"
    />

    <CancelRentalModal
      v-if="cancelTarget"
      :rental="cancelTarget"
      @close="closeCancelModal"
      @cancelled="onRentalCancelled"
    />
  </div>
</template>
