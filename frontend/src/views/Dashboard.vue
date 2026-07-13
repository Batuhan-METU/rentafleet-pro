<script setup>
// Ana gösterge paneli görünümü.
// Veri/iş mantığı useVehicles composable'ında; kabuk DefaultLayout'ta.
// Bu görünüm yalnızca içeriği (istatistikler + kart grid'i) düzenler ve
// sunuma özel filtre/arama durumunu tutar.
import { ref, computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import DefaultLayout from '../layouts/DefaultLayout.vue'
import VehicleCard from '../components/VehicleCard.vue'
import VehicleDetailModal from '../components/VehicleDetailModal.vue'
import LiveMap from '../components/LiveMap.vue'
import OverviewDashboard from '../components/overview/OverviewDashboard.vue'
import SettingsPage from '../components/settings/SettingsPage.vue'
import MaintenanceCenter from '../components/MaintenanceCenter.vue'
import DriverCard from '../components/DriverCard.vue'
import DriverDetailModal from '../components/DriverDetailModal.vue'
import { useDriverStore } from '../stores/driverStore.js'
import DriverFormModal from '../components/DriverFormModal.vue'
import PricingManager from '../components/PricingManager.vue'
import ReservationManager from '../components/ReservationManager.vue'
import RentalWorkflowProgress from '../components/RentalWorkflowProgress.vue'
import VehicleFormModal from '../components/VehicleFormModal.vue'
import { useFinanceStore } from '../stores/financeStore.js'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'
import { useRentalStore } from '../stores/rentalStore.js'
import { useVehicles } from '../composables/useVehicles.js'
import { useAuthStore } from '../stores/authStore.js'
import { useUiStore } from '../stores/uiStore.js'
import { VEHICLE_STATUS_LABELS } from '../utils/vehicleStatus.js'

const auth = useAuthStore()
const ui = useUiStore()
const finance = useFinanceStore()
const driverStore = useDriverStore()
const workflow = useRentalWorkflowStore()
const rentalStore = useRentalStore()
const { readyForDriverPick } = storeToRefs(workflow)
const { activeView } = storeToRefs(ui)
const { vehicles, loading, error, refresh } = useVehicles()
const selectedDriverId = ref(null)
const showDriverForm = ref(false)
const selectedVehicle = ref(null)
const driverSearch = ref('')

const showVehicleForm = ref(false)
const editVehicle = ref(null)
const editProfile = ref(null)

function openDriverDetail(driver) {
  selectedDriverId.value = driver.id
}

function closeDriverDetail() {
  selectedDriverId.value = null
}

function openDetail(vehicle) {
  selectedVehicle.value = vehicle
}

function closeDetail() {
  selectedVehicle.value = null
}

const searchQuery = ref('')
const statusFilter = ref('ALL')

const statusFilters = [
  { id: 'ALL', label: 'Tümü' },
  { id: 'AVAILABLE', label: VEHICLE_STATUS_LABELS.AVAILABLE },
  { id: 'RENTED', label: VEHICLE_STATUS_LABELS.RENTED },
  { id: 'MAINTENANCE', label: VEHICLE_STATUS_LABELS.MAINTENANCE },
]

const filteredVehicles = computed(() => {
  const q = searchQuery.value.trim().toLocaleLowerCase('tr')
  return vehicles.value.filter((vehicle) => {
    if (statusFilter.value !== 'ALL' && vehicle.status !== statusFilter.value) return false
    if (!q) return true
    return `${vehicle.plate_number} ${vehicle.brand} ${vehicle.model}`
      .toLocaleLowerCase('tr')
      .includes(q)
  })
})

const filteredDrivers = computed(() => {
  const q = driverSearch.value.trim().toLocaleLowerCase('tr')
  if (!q) return driverStore.drivers
  return driverStore.drivers.filter((d) =>
    `${d.ad_soyad} ${d.city} ${d.phone}`.toLocaleLowerCase('tr').includes(q),
  )
})

function refreshDrivers() {
  driverStore.fetchDrivers()
}

function openAddDriver() {
  showDriverForm.value = true
}

function onDriverSaved(driver) {
  showDriverForm.value = false
  refreshDrivers()

  if (workflow.active && driver) {
    const risk = driver.risk
    const approved = risk?.onaylandi ?? (!risk?.blokajlar?.length && (risk?.uygun_araclar?.length > 0))
    workflow.setDriver({
      id: driver.id,
      name: driver.ad_soyad ?? `${driver.first_name ?? ''} ${driver.last_name ?? ''}`.trim(),
      riskApproved: approved,
      depositAmount: risk?.depozito ? Number(risk.depozito) : null,
    })
    selectedDriverId.value = driver.id
  }
}

const quickReserveError = ref('')

async function quickAutoReserve(driver) {
  quickReserveError.value = ''
  if (!workflow.readyForDriverPick) {
    quickReserveError.value = 'Önce fiyatlandırmadan araç ve fiyat belirleyin.'
    return
  }
  if (driver.aktif_kiralama) {
    quickReserveError.value = 'Sürücünün zaten aktif kiralaması var.'
    return
  }
  try {
    await rentalStore.createRental({
      driver_id: driver.id,
      vehicle_id: workflow.vehicleId,
      pickup_date: workflow.pickupDate,
      dropoff_date: workflow.dropoffDate,
      quoted_total: workflow.agreedPrice ?? null,
      deposit_amount: workflow.depositAmount ?? null,
    })
    workflow.clear()
    await driverStore.fetchDrivers()
    await refresh()
    navigateToReservations()
  } catch (err) {
    quickReserveError.value = err?.response?.data?.error ?? 'Rezervasyon oluşturulamadı.'
    selectedDriverId.value = driver.id
  }
}

function navigateToReservations() {
  ui.navigate('reservations', { isFleetManager: auth.isFleetManager })
}

function navigateToDrivers() {
  ui.navigate('drivers', { isFleetManager: auth.isFleetManager })
}

function onGoReservation() {
  navigateToReservations()
}

async function onDriverReserved() {
  selectedDriverId.value = null
  await driverStore.fetchDrivers()
  await refresh()
}

function openAddVehicle() {
  editVehicle.value = null
  editProfile.value = null
  showVehicleForm.value = true
}

async function openEditVehicle(vehicle) {
  editVehicle.value = vehicle
  editProfile.value = await finance.fetchProfile(vehicle.id)
  showVehicleForm.value = true
  closeDetail()
}

async function onVehicleSaved() {
  showVehicleForm.value = false
  editVehicle.value = null
  editProfile.value = null
  await refresh()
}

onMounted(() => {
  ui.initNavigation(auth.isFleetManager)
  driverStore.fetchDrivers()
})

watch(activeView, (view) => {
  if (view === 'drivers') {
    driverStore.fetchDrivers()
  }
}, { immediate: true })
</script>

<template>
  <DefaultLayout @logout="auth.logout">
    <!-- Üst bar aksiyonları (arama + yenile) -->
    <template #actions="{ navigate: nav }">
      <div v-if="activeView === 'drivers'" class="relative hidden sm:block">
        <input
          v-model="driverSearch"
          type="search"
          placeholder="Ad, şehir veya telefon ara..."
          class="rf-input w-72"
        />
      </div>

      <div v-if="activeView === 'vehicles'" class="relative hidden sm:block">
        <svg class="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
        </svg>
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Plaka, marka veya model ara..."
          class="rf-input w-72 !pl-10"
        />
      </div>

      <button
        v-if="activeView === 'drivers'"
        type="button"
        class="rf-btn-primary"
        @click="openAddDriver"
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Sürücü Ekle
      </button>

      <button
        v-if="activeView === 'vehicles' && auth.isFleetManager"
        type="button"
        class="rf-btn-primary"
        @click="openAddVehicle"
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Araç Ekle
      </button>

      <button
        v-if="activeView !== 'live' && activeView !== 'maintenance' && activeView !== 'pricing' && activeView !== 'reservations' && activeView !== 'drivers' && activeView !== 'vehicles'"
        type="button"
        class="rf-btn-primary"
        :disabled="loading"
        @click="refresh"
      >
        <svg class="h-4 w-4" :class="{ 'animate-spin': loading }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Yenile
      </button>
    </template>

    <!-- İçerik -->
    <template #default="{ navigate: nav }">
      <div :key="activeView">
      <!-- Canlı Takip (araç listesi yüklemesinden bağımsız, kendi verisini çeker) -->
      <LiveMap v-if="activeView === 'live'" />

      <!-- Bakım Merkezi -->
      <MaintenanceCenter v-if="activeView === 'maintenance'" />

      <!-- Fiyatlandırma (yalnızca müdür menüsünde görünür) -->
      <PricingManager v-if="activeView === 'pricing'" />

      <!-- Rezervasyonlar -->
      <ReservationManager v-if="activeView === 'reservations'" />

      <!-- Sürücüler -->
      <div v-if="activeView === 'drivers'" class="space-y-6">
        <RentalWorkflowProgress
          v-if="readyForDriverPick"
          class="mb-4"
          @cancel="quickReserveError = ''"
        >
          <p class="mt-2 text-sm text-slate-600">
            Müşteri fiyatı kabul etti. Kayıtlı müşteriyi listeden seçip
            <strong>Otomatik Rezervasyon Yap</strong>'a basın. İlk kez gelen müşteri için sağ üstten
            <strong>Sürücü Ekle</strong> kullanın.
          </p>
          <p v-if="workflow.vehicleLabel" class="mt-2 text-xs font-semibold text-brand-700">
            Araç: {{ workflow.vehicleLabel }} · {{ workflow.agreedPrice }} ₺
            <span v-if="workflow.pickupDate && workflow.dropoffDate">
              · {{ workflow.pickupDate }} → {{ workflow.dropoffDate }}
            </span>
          </p>
          <p v-if="quickReserveError" class="mt-2 text-sm text-rose-700">{{ quickReserveError }}</p>
        </RentalWorkflowProgress>

        <div v-if="driverStore.loading && !driverStore.drivers.length" class="grid place-items-center py-16">
          <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
        </div>
        <div v-else-if="driverStore.error" class="text-center text-red-600">Sürücü listesi yüklenemedi.</div>
        <div v-else>
          <div class="mb-4 flex items-center justify-between">
            <span class="rf-capsule !py-1.5 text-sm text-slate-600">
              <span class="font-black text-slate-900">{{ filteredDrivers.length }}</span> sürücü
            </span>
            <button type="button" class="text-sm font-bold text-brand-600 transition-all duration-300 hover:translate-x-0.5" @click="refreshDrivers">Yenile</button>
          </div>
          <div v-if="filteredDrivers.length" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <DriverCard
              v-for="driver in filteredDrivers"
              :key="driver.id"
              :driver="driver"
              @select="openDriverDetail"
              @auto-reserve="quickAutoReserve"
            />
          </div>
          <p v-else class="rf-glass rounded-3xl p-12 text-center text-slate-500">
            Sürücü bulunamadı.
          </p>
        </div>
      </div>

      <!-- Yükleniyor (araç verisi) -->
      <div v-if="loading && activeView === 'vehicles'" class="grid h-full place-items-center">
        <div class="text-center">
          <div class="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
          <p class="mt-4 text-base font-semibold text-slate-700">Veriler yükleniyor...</p>
          <p class="mt-1 text-sm text-slate-500">Filo bilgileri sunucudan alınıyor.</p>
        </div>
      </div>

      <!-- Hata (araç verisi) -->
      <div v-if="error && activeView === 'vehicles'" class="grid h-full place-items-center">
        <div class="max-w-md rf-glass-strong rounded-3xl p-10 text-center">
          <div class="mx-auto grid h-14 w-14 place-items-center rounded-full bg-red-100 text-2xl font-bold text-red-600">!</div>
          <p class="mt-4 text-lg font-bold text-slate-800">Veri çekilirken bir hata oluştu</p>
          <p class="mt-1 text-sm text-slate-500">
            Sunucuya ulaşılamadı. Backend servisinin çalıştığından emin olup tekrar deneyin.
          </p>
          <button
            type="button"
            class="rf-btn-primary mt-5"
            @click="refresh"
          >
            Tekrar Dene
          </button>
        </div>
      </div>

      <!-- Ev -->
      <OverviewDashboard v-if="activeView === 'overview'" :navigate="nav" />

      <!-- Ayarlar -->
      <SettingsPage v-if="activeView === 'settings'" />

      <!-- Araçlar -->
      <template v-if="activeView === 'vehicles'">
        <div class="mb-5 flex flex-wrap items-center gap-2">
          <button
            v-for="f in statusFilters"
            :key="f.id"
            type="button"
            class="rf-pill-filter"
            :class="statusFilter === f.id ? 'rf-pill-filter--active' : 'rf-pill-filter--idle'"
            @click="statusFilter = f.id"
          >
            {{ f.label }}
          </button>
          <span class="rf-capsule !py-1.5 ml-auto text-sm text-slate-600">
            <span class="font-black text-slate-900">{{ filteredVehicles.length }}</span> araç
          </span>
        </div>

        <div v-if="filteredVehicles.length" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <VehicleCard v-for="vehicle in filteredVehicles" :key="vehicle.id" :vehicle="vehicle" @select="openDetail" />
        </div>
        <div v-else class="rf-glass grid place-items-center rounded-3xl p-16 text-center">
          <div class="grid h-14 w-14 place-items-center rounded-full bg-slate-100 text-2xl text-slate-400">∅</div>
          <p class="mt-4 text-base font-semibold text-slate-700">Aramanızla eşleşen araç bulunamadı</p>
          <p class="mt-1 text-sm text-slate-500">Filtreleri veya arama terimini değiştirmeyi deneyin.</p>
        </div>
      </template>
      </div>
    </template>
  </DefaultLayout>

  <VehicleDetailModal
    v-if="selectedVehicle"
    :vehicle="selectedVehicle"
    @close="closeDetail"
    @edit="openEditVehicle"
  />

  <VehicleFormModal
    v-if="showVehicleForm"
    :edit-vehicle="editVehicle"
    :edit-profile="editProfile"
    @close="showVehicleForm = false"
    @saved="onVehicleSaved"
  />

  <DriverDetailModal
    v-if="selectedDriverId"
    :driver-id="selectedDriverId"
    @close="closeDriverDetail"
    @go-reservation="onGoReservation"
    @reserved="onDriverReserved"
  />

  <DriverFormModal
    v-if="showDriverForm"
    @close="showDriverForm = false"
    @saved="onDriverSaved"
  />
</template>
