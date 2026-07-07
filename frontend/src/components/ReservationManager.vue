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
import { formatTL } from '../utils/format.js'

const rentalStore = useRentalStore()
const workflow = useRentalWorkflowStore()
const { readyForDriverPick } = storeToRefs(workflow)
const vehicleStore = useVehicleStore()
const driverStore = useDriverStore()
const ui = useUiStore()
const auth = useAuthStore()

const listTab = ref('AKTIF')
const showManualForm = ref(false)
const formError = ref('')
const successMessage = ref('')

const tabs = [
  { id: 'AKTIF', label: 'Aktif', countKey: 'aktif' },
  { id: 'GELECEK', label: 'Gelecek', countKey: 'gelecek' },
  { id: 'GECMIS', label: 'Geçmiş', countKey: 'gecmis' },
]

const dateFormatter = new Intl.DateTimeFormat('tr-TR', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
})

function formatDate(iso) {
  if (!iso) return '—'
  try {
    return dateFormatter.format(new Date(iso))
  } catch {
    return iso
  }
}

function addDays(base, days) {
  const d = new Date(base)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

const minPickup = addDays(new Date(), 1)

const availableVehicles = computed(() =>
  vehicleStore.vehicles.filter((v) => v.status === 'AVAILABLE'),
)

const listedRentals = computed(() => {
  if (listTab.value === 'AKTIF') return rentalStore.activeRentals
  if (listTab.value === 'GELECEK') return rentalStore.upcomingRentals
  return rentalStore.pastRentals
})

function parsePrice(raw) {
  if (!raw) return null
  const n = Number(String(raw).replace(/\s/g, '').replace(/\./g, '').replace(',', '.'))
  return Number.isNaN(n) || n <= 0 ? null : n
}

function emptyForm() {
  return {
    driverId: '',
    vehicleId: '',
    pickupDate: addDays(new Date(), 1),
    dropoffDate: addDays(new Date(), 4),
    quotedTotal: '',
  }
}

const workflowForm = ref({
  pickupDate: '',
  dropoffDate: '',
  quotedTotal: '',
})

const manualForm = ref(emptyForm())

watch(
  () => workflow.pickupDate,
  (v) => {
    if (v) {
      workflowForm.value.pickupDate = v
      if (!manualForm.value.pickupDate || workflow.canCreateReservation) {
        manualForm.value.pickupDate = v
      }
    }
  },
  { immediate: true },
)

watch(
  () => workflow.dropoffDate,
  (v) => {
    if (v) {
      workflowForm.value.dropoffDate = v
      if (!manualForm.value.dropoffDate || workflow.canCreateReservation) {
        manualForm.value.dropoffDate = v
      }
    }
  },
  { immediate: true },
)

watch(
  () => workflow.agreedPrice,
  (v) => {
    if (v != null) {
      workflowForm.value.quotedTotal = String(v)
      manualForm.value.quotedTotal = String(v)
    }
  },
  { immediate: true },
)

watch(
  () => workflow.driverId,
  (id) => {
    if (id) manualForm.value.driverId = id
  },
  { immediate: true },
)

watch(
  () => workflow.vehicleId,
  (id) => {
    if (id) manualForm.value.vehicleId = id
  },
  { immediate: true },
)

async function createReservation(payload, { clearWorkflow = false } = {}) {
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
      quoted_total: payload.quoted_total ?? null,
      deposit_amount: payload.deposit_amount ?? null,
    })
    successMessage.value = 'Rezervasyon oluşturuldu. Araç sürücüye atandı.'
    if (clearWorkflow) workflow.clear()
    manualForm.value = emptyForm()
    await vehicleStore.fetchVehicles()
    await driverStore.fetchDrivers()
    await rentalStore.fetchRentals()
    return true
  } catch (err) {
    formError.value = err?.response?.data?.error ?? 'Rezervasyon oluşturulamadı.'
    return false
  }
}

async function submitWorkflowReservation() {
  await createReservation({
    driver_id: workflow.driverId,
    vehicle_id: workflow.vehicleId,
    pickup_date: workflowForm.value.pickupDate,
    dropoff_date: workflowForm.value.dropoffDate,
    quoted_total: parsePrice(workflowForm.value.quotedTotal) ?? workflow.agreedPrice,
    deposit_amount: workflow.depositAmount,
  }, { clearWorkflow: true })
}

async function submitManualReservation() {
  await createReservation({
    driver_id: manualForm.value.driverId,
    vehicle_id: manualForm.value.vehicleId,
    pickup_date: manualForm.value.pickupDate,
    dropoff_date: manualForm.value.dropoffDate,
    quoted_total: parsePrice(manualForm.value.quotedTotal),
  })
}

const cancelError = ref('')

async function cancelReservation(rental) {
  cancelError.value = ''
  if (!window.confirm(`${rental.surucu_adi} için rezervasyonu iptal etmek istediğinize emin misiniz?`)) {
    return
  }
  try {
    await rentalStore.cancelRental(rental.id)
    await vehicleStore.fetchVehicles()
    await driverStore.fetchDrivers()
    successMessage.value = 'Rezervasyon iptal edildi.'
  } catch (err) {
    cancelError.value = err?.response?.data?.error ?? 'Rezervasyon iptal edilemedi.'
  }
}

function canCancelRental(rental) {
  return rental.donem_kodu === 'AKTIF' || rental.donem_kodu === 'GELECEK'
}

function donemBadgeClass(kod) {
  if (kod === 'AKTIF') return 'bg-emerald-100 text-emerald-700'
  if (kod === 'GELECEK') return 'bg-sky-100 text-sky-700'
  return 'bg-slate-100 text-slate-600'
}

onMounted(async () => {
  if (!vehicleStore.vehicles.length) await vehicleStore.fetchVehicles()
  if (!driverStore.drivers.length) await driverStore.fetchDrivers()
  await rentalStore.fetchRentals()
  if (workflow.canCreateReservation) showManualForm.value = false
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

    <!-- Süreçten gelen hızlı rezervasyon -->
    <RentalWorkflowProgress v-if="workflow.active && workflow.step === 'reservation'">
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
      <h3 class="text-lg font-black text-slate-900">Süreçten Gelen Rezervasyon</h3>
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
          <input v-model="workflowForm.pickupDate" type="date" :min="minPickup" class="rf-input mt-1" />
        </div>
        <div>
          <label class="text-xs font-medium text-slate-500">Bırakış Tarihi</label>
          <input v-model="workflowForm.dropoffDate" type="date" :min="workflowForm.pickupDate || minPickup" class="rf-input mt-1" />
        </div>
        <div>
          <label class="text-xs font-medium text-slate-500">Toplam Fiyat (₺)</label>
          <input v-model="workflowForm.quotedTotal" type="text" class="rf-input mt-1" />
        </div>
      </div>

      <button
        type="button"
        class="rf-btn-primary mt-5"
        :disabled="rentalStore.creating"
        @click="submitWorkflowReservation"
      >
        {{ rentalStore.creating ? 'Oluşturuluyor…' : 'Rezervasyonu Onayla ve Aracı Ata' }}
      </button>
    </div>

    <!-- Manuel rezervasyon -->
    <div class="rf-glass-strong rounded-3xl p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 class="text-lg font-black text-slate-900">Manuel Rezervasyon</h3>
          <p class="mt-1 text-sm text-slate-500">Sürücü ve aracı elle seçerek rezervasyon oluşturun.</p>
        </div>
        <button type="button" class="rf-btn-ghost text-sm" @click="showManualForm = !showManualForm">
          {{ showManualForm ? 'Formu Gizle' : 'Yeni Rezervasyon' }}
        </button>
      </div>

      <div v-if="showManualForm" class="mt-5 border-t border-white/30 pt-5">
        <div class="grid gap-4 sm:grid-cols-2">
          <div>
            <label class="text-xs font-medium text-slate-500">Sürücü</label>
            <select v-model="manualForm.driverId" class="rf-input mt-1">
              <option value="">Seçin…</option>
              <option v-for="d in driverStore.drivers" :key="d.id" :value="d.id">
                {{ d.ad_soyad }} — {{ d.phone }}
              </option>
            </select>
          </div>
          <div>
            <label class="text-xs font-medium text-slate-500">Araç</label>
            <select v-model="manualForm.vehicleId" class="rf-input mt-1">
              <option value="">Seçin…</option>
              <option v-for="v in availableVehicles" :key="v.id" :value="v.id">
                {{ v.plate_number }} — {{ v.brand }} {{ v.model }}
              </option>
            </select>
          </div>
          <div>
            <label class="text-xs font-medium text-slate-500">Alış Tarihi</label>
            <input v-model="manualForm.pickupDate" type="date" :min="minPickup" class="rf-input mt-1" />
          </div>
          <div>
            <label class="text-xs font-medium text-slate-500">Bırakış Tarihi</label>
            <input v-model="manualForm.dropoffDate" type="date" :min="manualForm.pickupDate || minPickup" class="rf-input mt-1" />
          </div>
          <div class="sm:col-span-2">
            <label class="text-xs font-medium text-slate-500">Toplam Fiyat (₺)</label>
            <input v-model="manualForm.quotedTotal" type="text" class="rf-input mt-1" placeholder="Opsiyonel" />
          </div>
        </div>
        <button
          type="button"
          class="rf-btn-primary mt-4"
          :disabled="rentalStore.creating"
          @click="submitManualReservation"
        >
          {{ rentalStore.creating ? 'Kaydediliyor…' : 'Manuel Rezervasyon Oluştur' }}
        </button>
      </div>
    </div>

    <!-- Liste: aktif / gelecek / geçmiş -->
    <div class="rf-glass-strong rounded-3xl p-6">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h3 class="text-lg font-black text-slate-900">Rezervasyon Kayıtları</h3>
        <button type="button" class="text-sm font-bold text-brand-600" @click="rentalStore.fetchRentals()">
          Yenile
        </button>
      </div>

      <div v-if="cancelError" class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
        {{ cancelError }}
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
          <span class="ml-1 opacity-70">({{ rentalStore.summary[tab.countKey] ?? 0 }})</span>
        </button>
      </div>

      <div v-if="rentalStore.loading" class="grid place-items-center py-12">
        <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600" />
      </div>
      <p v-else-if="rentalStore.error" class="py-8 text-center text-red-600">Liste yüklenemedi.</p>
      <div v-else-if="listedRentals.length" class="mt-4 overflow-x-auto">
        <table class="w-full min-w-[640px] text-left text-sm">
          <thead>
            <tr class="border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
              <th class="pb-3 pr-4">Sürücü</th>
              <th class="pb-3 pr-4">Araç</th>
              <th class="pb-3 pr-4">Alış</th>
              <th class="pb-3 pr-4">Bırakış</th>
              <th class="pb-3 pr-4">Dönem</th>
              <th class="pb-3 pr-4">Fiyat</th>
              <th class="pb-3">İşlem</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in listedRentals"
              :key="r.id"
              class="border-b border-slate-100"
            >
              <td class="py-3 pr-4 font-semibold text-slate-800">{{ r.surucu_adi }}</td>
              <td class="py-3 pr-4">
                <span class="font-bold">{{ r.plaka }}</span>
                <span class="ml-1 text-slate-500">{{ r.marka_model }}</span>
              </td>
              <td class="py-3 pr-4 text-slate-600">{{ formatDate(r.started_at) }}</td>
              <td class="py-3 pr-4 text-slate-600">{{ formatDate(r.ended_at) }}</td>
              <td class="py-3 pr-4">
                <span class="rounded-full px-2 py-0.5 text-xs font-bold" :class="donemBadgeClass(r.donem_kodu)">
                  {{ r.donem_label }}
                </span>
              </td>
              <td class="py-3 pr-4 font-semibold text-slate-800">
                {{ r.quoted_total ? formatTL(r.quoted_total, { decimals: true }) : '—' }}
              </td>
              <td class="py-3">
                <button
                  v-if="canCancelRental(r)"
                  type="button"
                  class="text-xs font-bold text-rose-600 hover:text-rose-800"
                  :disabled="rentalStore.cancellingId === r.id"
                  @click="cancelReservation(r)"
                >
                  {{ rentalStore.cancellingId === r.id ? 'İptal…' : 'Rezervasyonu İptal' }}
                </button>
                <span v-else class="text-xs text-slate-400">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="py-10 text-center text-slate-500">
        Bu kategoride rezervasyon yok.
      </p>
    </div>
  </div>
</template>
