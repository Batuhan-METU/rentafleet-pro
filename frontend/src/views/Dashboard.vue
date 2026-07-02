<script setup>
// Ana gösterge paneli görünümü.
// Veri/iş mantığı useVehicles composable'ında; kabuk DefaultLayout'ta.
// Bu görünüm yalnızca içeriği (istatistikler + kart grid'i) düzenler ve
// sunuma özel filtre/arama durumunu tutar.
import { ref, computed, onMounted } from 'vue'
import DefaultLayout from '../layouts/DefaultLayout.vue'
import VehicleCard from '../components/VehicleCard.vue'
import VehicleDetailModal from '../components/VehicleDetailModal.vue'
import LiveMap from '../components/LiveMap.vue'
import FleetStats from '../components/FleetStats.vue'
import FleetCharts from '../components/FleetCharts.vue'
import MaintenanceCenter from '../components/MaintenanceCenter.vue'
import DriverCard from '../components/DriverCard.vue'
import DriverDetailModal from '../components/DriverDetailModal.vue'
import { useDriverStore } from '../stores/driverStore.js'
import PricingManager from '../components/PricingManager.vue'
import { useVehicles } from '../composables/useVehicles.js'
import { useAuthStore } from '../stores/authStore.js'

const auth = useAuthStore()
const driverStore = useDriverStore()
const { vehicles, loading, error, refresh } = useVehicles()
const selectedDriverId = ref(null)
const selectedVehicle = ref(null)
const driverSearch = ref('')

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
  { id: 'AVAILABLE', label: 'Müsait' },
  { id: 'RENTED', label: 'Kirada' },
  { id: 'MAINTENANCE', label: 'Bakımda' },
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

const recentVehicles = computed(() => vehicles.value.slice(0, 8))

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

onMounted(() => {
  driverStore.fetchDrivers()
})
</script>

<template>
  <DefaultLayout @logout="auth.logout">
    <!-- Üst bar aksiyonları (arama + yenile) -->
    <template #actions="{ activeView }">
      <div v-if="activeView === 'drivers'" class="relative hidden sm:block">
        <input
          v-model="driverSearch"
          type="search"
          placeholder="Ad, şehir veya telefon ara..."
          class="w-72 rounded-lg border border-slate-200 bg-slate-50 py-2 pl-3 pr-3 text-sm text-slate-700 outline-none transition focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-100"
        />
      </div>

      <div v-if="activeView === 'vehicles'" class="relative hidden sm:block">
        <svg class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-4.35-4.35M17 11a6 6 0 11-12 0 6 6 0 0112 0z" />
        </svg>
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Plaka, marka veya model ara..."
          class="w-72 rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-3 text-sm text-slate-700 outline-none transition focus:border-brand-500 focus:bg-white focus:ring-2 focus:ring-brand-100"
        />
      </div>

      <button
        v-if="activeView !== 'live' && activeView !== 'maintenance' && activeView !== 'pricing' && activeView !== 'drivers'"
        type="button"
        class="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:opacity-60"
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
    <template #default="{ activeView, navigate }">
      <!-- Canlı Takip (araç listesi yüklemesinden bağımsız, kendi verisini çeker) -->
      <LiveMap v-if="activeView === 'live'" />

      <!-- Bakım Merkezi -->
      <MaintenanceCenter v-else-if="activeView === 'maintenance'" />

      <!-- Fiyatlandırma (yalnızca müdür menüsünde görünür) -->
      <PricingManager v-else-if="activeView === 'pricing'" />

      <!-- Sürücüler -->
      <template v-else-if="activeView === 'drivers'">
        <div v-if="driverStore.loading && !driverStore.drivers.length" class="grid place-items-center py-16">
          <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
        </div>
        <div v-else-if="driverStore.error" class="text-center text-red-600">Sürücü listesi yüklenemedi.</div>
        <div v-else>
          <div class="mb-4 flex items-center justify-between">
            <p class="text-sm text-slate-500">{{ filteredDrivers.length }} sürücü listeleniyor</p>
            <button type="button" class="text-sm font-semibold text-brand-600" @click="refreshDrivers">Yenile</button>
          </div>
          <div v-if="filteredDrivers.length" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            <DriverCard v-for="driver in filteredDrivers" :key="driver.id" :driver="driver" @select="openDriverDetail" />
          </div>
          <p v-else class="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center text-slate-500">
            Sürücü bulunamadı.
          </p>
        </div>
      </template>

      <!-- Yükleniyor (araç verisi) -->
      <div v-else-if="loading && (activeView === 'overview' || activeView === 'vehicles')" class="grid h-full place-items-center">
        <div class="text-center">
          <div class="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
          <p class="mt-4 text-base font-semibold text-slate-700">Veriler yükleniyor...</p>
          <p class="mt-1 text-sm text-slate-500">Filo bilgileri sunucudan alınıyor.</p>
        </div>
      </div>

      <!-- Hata (araç verisi) -->
      <div v-else-if="error && (activeView === 'overview' || activeView === 'vehicles')" class="grid h-full place-items-center">
        <div class="max-w-md rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">
          <div class="mx-auto grid h-14 w-14 place-items-center rounded-full bg-red-100 text-2xl font-bold text-red-600">!</div>
          <p class="mt-4 text-lg font-bold text-slate-800">Veri çekilirken bir hata oluştu</p>
          <p class="mt-1 text-sm text-slate-500">
            Sunucuya ulaşılamadı. Backend servisinin çalıştığından emin olup tekrar deneyin.
          </p>
          <button
            type="button"
            class="mt-5 rounded-lg bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700"
            @click="refresh"
          >
            Tekrar Dene
          </button>
        </div>
      </div>

      <!-- Genel Bakış -->
      <template v-else-if="activeView === 'overview'">
        <!-- Metrik kartları -->
        <FleetStats />

        <!-- Analitik grafikler -->
        <FleetCharts class="mt-6" />

        <div class="mt-8 flex items-center justify-between">
          <h2 class="text-lg font-bold text-slate-900">Son Eklenen Araçlar</h2>
          <button type="button" class="text-sm font-semibold text-brand-600 hover:text-brand-700" @click="navigate('vehicles')">
            Tümünü gör →
          </button>
        </div>

        <div v-if="recentVehicles.length" class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <VehicleCard v-for="vehicle in recentVehicles" :key="vehicle.id" :vehicle="vehicle" @select="openDetail" />
        </div>
        <p v-else class="mt-4 rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          Görüntülenecek araç bulunamadı.
        </p>
      </template>

      <!-- Araçlar -->
      <template v-else-if="activeView === 'vehicles'">
        <div class="mb-5 flex flex-wrap items-center gap-2">
          <button
            v-for="f in statusFilters"
            :key="f.id"
            type="button"
            class="rounded-full px-4 py-1.5 text-sm font-medium transition"
            :class="statusFilter === f.id
              ? 'bg-brand-600 text-white shadow-sm'
              : 'border border-slate-200 bg-white text-slate-600 hover:bg-slate-50'"
            @click="statusFilter = f.id"
          >
            {{ f.label }}
          </button>
          <span class="ml-auto text-sm text-slate-500">{{ filteredVehicles.length }} araç listeleniyor</span>
        </div>

        <div v-if="filteredVehicles.length" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <VehicleCard v-for="vehicle in filteredVehicles" :key="vehicle.id" :vehicle="vehicle" @select="openDetail" />
        </div>
        <div v-else class="grid place-items-center rounded-xl border border-dashed border-slate-300 bg-white p-16 text-center">
          <div class="grid h-14 w-14 place-items-center rounded-full bg-slate-100 text-2xl text-slate-400">∅</div>
          <p class="mt-4 text-base font-semibold text-slate-700">Aramanızla eşleşen araç bulunamadı</p>
          <p class="mt-1 text-sm text-slate-500">Filtreleri veya arama terimini değiştirmeyi deneyin.</p>
        </div>
      </template>
    </template>
  </DefaultLayout>

  <VehicleDetailModal
    v-if="selectedVehicle"
    :vehicle="selectedVehicle"
    @close="closeDetail"
  />

  <DriverDetailModal
    v-if="selectedDriverId"
    :driver-id="selectedDriverId"
    @close="closeDriverDetail"
  />
</template>
