<script setup>
// Ana gösterge paneli görünümü.
// Veri/iş mantığı useVehicles composable'ında; kabuk DefaultLayout'ta.
// Bu görünüm yalnızca içeriği (istatistikler + kart grid'i) düzenler ve
// sunuma özel filtre/arama durumunu tutar.
import { ref, computed, onMounted, watch, defineAsyncComponent } from 'vue'
import { storeToRefs } from 'pinia'
import DefaultLayout from '../layouts/DefaultLayout.vue'
import VehicleListRow from '../components/VehicleListRow.vue'
import OverviewDashboard from '../components/overview/OverviewDashboard.vue'
import DriverListRow from '../components/DriverListRow.vue'
import { useDriverStore } from '../stores/driverStore.js'
import { useLoanStore } from '../stores/loanStore.js'
import RentalWorkflowProgress from '../components/RentalWorkflowProgress.vue'
import { useFinanceStore } from '../stores/financeStore.js'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'
import { useRentalStore } from '../stores/rentalStore.js'
import { useVehicles } from '../composables/useVehicles.js'
import { downloadExcelReport } from '../utils/exportExcel.js'
import { getApiErrorMessage } from '../utils/apiError.js'
import { useAuthStore } from '../stores/authStore.js'
import { useUiStore } from '../stores/uiStore.js'
import { VEHICLE_STATUS_LABELS } from '../utils/vehicleStatus.js'

// "Ev" (OverviewDashboard) dışındaki tüm görünümler/modallar tembel yüklenir
// — aynı anda tek bir `activeView` gösterildiği için geri kalanı ilk açılışta
// hiç gerekmez (bkz. audit bulgusu #34, tek 587KB paket sorunu). LiveMap
// özellikle önemli: Leaflet haritalama kütüphanesini kendi paketine taşır,
// bunu hiç kullanmayan (yönetici olmayan) kullanıcılar onu asla indirmez.
const LiveMap = defineAsyncComponent(() => import('../components/LiveMap.vue'))
const MaintenanceCenter = defineAsyncComponent(() => import('../components/MaintenanceCenter.vue'))
const PricingManager = defineAsyncComponent(() => import('../components/finance/PricingManager.vue'))
const RentalManager = defineAsyncComponent(() => import('../components/RentalManager.vue'))
const LoansManager = defineAsyncComponent(() => import('../components/finance/LoansManager.vue'))
const LoanDetailPage = defineAsyncComponent(() => import('./LoanDetailPage.vue'))
const VehicleDetailPage = defineAsyncComponent(() => import('./VehicleDetailPage.vue'))
const DriverDetailPage = defineAsyncComponent(() => import('./DriverDetailPage.vue'))
const VehicleFormModal = defineAsyncComponent(() => import('../components/VehicleFormModal.vue'))
const DriverFormModal = defineAsyncComponent(() => import('../components/DriverFormModal.vue'))
const ManualRentalModal = defineAsyncComponent(() => import('../components/ManualRentalModal.vue'))

const auth = useAuthStore()
const ui = useUiStore()
const finance = useFinanceStore()
const driverStore = useDriverStore()
const workflow = useRentalWorkflowStore()
const rentalStore = useRentalStore()
const loanStore = useLoanStore()
const { readyForDriverPick } = storeToRefs(workflow)
const { activeView, activeDriverId, activeLoanId } = storeToRefs(ui)
const { vehicles, loading, error, refresh } = useVehicles()
const { selectedDriver: detailDriver, rentalHistory: detailDriverRentals } = storeToRefs(driverStore)
const showDriverForm = ref(false)
const driverSearch = ref('')

const showVehicleForm = ref(false)
const editVehicle = ref(null)
const editProfile = ref(null)
const editPolicies = ref([])
const editRegistrationDetail = ref(null)

const showRentalModal = ref(false)

async function onRentalCreated() {
  showRentalModal.value = false
  await Promise.all([refresh(), driverStore.fetchDrivers(), rentalStore.fetchRentals()])
}

function openDriverDetail(driver) {
  ui.openDriverDetail(driver.id)
}

function closeDriverDetail() {
  ui.closeDriverDetail()
}

function openDetail(vehicle) {
  ui.openVehicleDetail(vehicle.id)
}

const detailVehicle = computed(() =>
  vehicles.value.find((v) => v.id === ui.activeVehicleId) ?? null,
)

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
    // Prefix eşleşmesi: "au" yazınca sadece "Audi" gibi AU ile BAŞLAYAN
    // plaka/marka/model eşleşir — herhangi bir yerde geçen değil.
    const plate = (vehicle.plate_number || '').toLocaleLowerCase('tr')
    const brand = (vehicle.brand || '').toLocaleLowerCase('tr')
    const model = (vehicle.model || '').toLocaleLowerCase('tr')
    return plate.startsWith(q) || brand.startsWith(q) || model.startsWith(q)
  })
})

// --- Toplu Excel dışa aktarma ------------------------------------------
// Ekrandaki arama/durum filtresi backend'e aynen iletilir: filtre varsa
// yalnızca filtrelenen araçlar, yoksa tüm filo indirilir.
const exportingExcel = ref(false)
const exportError = ref('')
let exportErrorTimer = null

async function exportFleetExcel() {
  if (exportingExcel.value) return
  exportingExcel.value = true
  exportError.value = ''
  try {
    const params = {}
    if (statusFilter.value !== 'ALL') params.status = statusFilter.value
    const q = searchQuery.value.trim()
    if (q) params.q = q

    await downloadExcelReport('vehicles/export/', {
      params,
      filenamePrefix: 'Filo_Envanter_Raporu',
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

const filteredDrivers = computed(() => {
  const q = driverSearch.value.trim().toLocaleLowerCase('tr')
  if (!q) return driverStore.drivers
  return driverStore.drivers.filter((d) =>
    `${d.full_name} ${d.city} ${d.phone}`.toLocaleLowerCase('tr').includes(q),
  )
})

function refreshDrivers() {
  const vehicleId = workflow.active && workflow.vehicleId ? workflow.vehicleId : null
  driverStore.fetchDrivers({ vehicleId })
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
    // Depozito, aracın fiyatı değil anlaşılan kiralama fiyatının bir
    // yüzdesidir — backend yalnızca oranı döner, tutar burada hesaplanır.
    const depositAmount = (risk?.depozito_orani != null && workflow.agreedPrice != null)
      ? Number(risk.depozito_orani) * Number(workflow.agreedPrice)
      : null
    workflow.setDriver({
      id: driver.id,
      name: driver.full_name ?? `${driver.first_name ?? ''} ${driver.last_name ?? ''}`.trim(),
      riskApproved: approved,
      depositAmount,
    })
    ui.openDriverDetail(driver.id)
  }
}

const quickRentError = ref('')

async function quickAutoRent(driver) {
  quickRentError.value = ''
  if (!workflow.readyForDriverPick) {
    quickRentError.value = 'Önce fiyatlandırmadan araç ve fiyat belirleyin.'
    return
  }
  if (driver.active_rental) {
    quickRentError.value = 'Sürücünün zaten aktif kiralaması var.'
    return
  }
  try {
    await rentalStore.createRental({
      driver_id: driver.id,
      vehicle_id: workflow.vehicleId,
      pickup_date: workflow.pickupDate,
      dropoff_date: workflow.dropoffDate,
      daily_rate: workflow.agreedDailyRate ?? null,
      deposit_amount: workflow.depositAmount ?? null,
    })
    workflow.clear()
    await driverStore.fetchDrivers()
    await refresh()
    navigateToRentals()
  } catch (err) {
    quickRentError.value = getApiErrorMessage(err, 'Kiralama oluşturulamadı.')
    ui.openDriverDetail(driver.id)
  }
}

function navigateToRentals() {
  ui.navigate('rentals', { isFleetManager: auth.isFleetManager })
}

function onGoRental() {
  navigateToRentals()
}

async function onDriverRented() {
  ui.closeDriverDetail()
  await driverStore.fetchDrivers()
  await refresh()
}

function openAddVehicle() {
  editVehicle.value = null
  editProfile.value = null
  editPolicies.value = []
  editRegistrationDetail.value = null
  showVehicleForm.value = true
}

async function openEditVehicle(vehicle) {
  editVehicle.value = vehicle
  const [profile, policies, registrationDetail] = await Promise.all([
    finance.fetchProfile(vehicle.id),
    finance.fetchInsurancePolicies(vehicle.id),
    finance.fetchRegistrationDetail(vehicle.id),
  ])
  editProfile.value = profile
  editPolicies.value = policies
  editRegistrationDetail.value = registrationDetail
  showVehicleForm.value = true
}

async function onVehicleSaved(savedVehicle) {
  showVehicleForm.value = false
  editVehicle.value = null
  editProfile.value = null
  editPolicies.value = []
  editRegistrationDetail.value = null
  // Kayıt yanıtı güncel poliçeleri de içeriyor (bkz. VehicleWriteSerializer.
  // to_representation) — store'daki poliçe önbelleğini burada tazeleyerek,
  // hâlâ açık olan "Poliçeler" sekmesinin bayat veri göstermesini önlüyoruz
  // (o bileşen sadece mount olduğunda fetch ediyor, kaydetme onu tetiklemez).
  if (savedVehicle?.id && savedVehicle.insurance_policies) {
    finance.insurancePoliciesById = {
      ...finance.insurancePoliciesById,
      [savedVehicle.id]: savedVehicle.insurance_policies,
    }
  }
  // Aynı mantık operasyon giderleri için — kayıt yanıtı güncel listeyi
  // içeriyor (VehicleWriteSerializer.to_representation), burada
  // tazelenmezse "Operasyon Gider Kırılımı" modalı bir sonraki açılışta
  // hâlâ eski/boş önbelleği gösterebilir.
  if (savedVehicle?.id && savedVehicle.operating_expenses) {
    finance.expensesById = {
      ...finance.expensesById,
      [savedVehicle.id]: savedVehicle.operating_expenses,
    }
  }
  // Araç Detayı'ndaki "Gelir & Gider Özeti"nin Operasyon tutarı, kayıt
  // yanıtında GELMEYEN ayrı uçlardan (yıllık özet + ömür-boyu maliyet
  // analizi) besleniyor — bunlar burada tazelenmezse, Düzenle penceresi
  // kapandıktan sonra Araç Detayı hâlâ eski toplamı göstermeye devam eder
  // (o bileşen bu verileri sadece kendi mount'unda çekiyor).
  if (savedVehicle?.id) {
    await Promise.allSettled([
      finance.fetchYearlySummary(savedVehicle.id),
      finance.fetchCostAnalysis(savedVehicle.id),
    ])
  }
  await refresh()
}

onMounted(() => {
  ui.initNavigation(auth.isFleetManager)
  refreshDrivers()
})

watch(activeView, (view) => {
  if (view === 'drivers') {
    refreshDrivers()
  }
}, { immediate: true })

// Sürücü detay sayfası (Araç Detayı ile aynı desen) — hash/ui.activeDriverId
// değiştiğinde ilgili sürücünün tam kaydını (risk, profil, kiralama geçmişi)
// çeker. Liste satırlarındaki özet veri risk/profile_summary içermiyor.
watch(activeDriverId, (id) => {
  if (id != null) {
    driverStore.fetchDriverDetail(id)
  } else {
    driverStore.clearSelectedDriver()
  }
}, { immediate: true })

// Kredi detay sayfası (Araç/Sürücü Detayı ile aynı desen) — hash/
// ui.activeLoanId değiştiğinde ilgili kredinin taksit planı + araç
// tahsislerini çeker.
watch(activeLoanId, (id) => {
  if (id != null) {
    loanStore.fetchLoanDetail(id)
  } else {
    loanStore.clearLoanDetail()
  }
}, { immediate: true })

watch(
  () => [workflow.active, workflow.vehicleId],
  () => {
    if (activeView.value === 'drivers' && workflow.active) {
      refreshDrivers()
    }
  },
)
</script>

<template>
  <DefaultLayout @logout="auth.logout">
    <!-- Üst bar aksiyonları (arama + yenile) -->
    <template #actions>
      <div v-if="activeView === 'drivers'" class="relative hidden sm:block">
        <input
          v-model="driverSearch"
          type="search"
          placeholder="Ad, şehir veya telefon ara..."
          class="rf-input w-72 !border-transparent !bg-brand-50/60 placeholder:text-slate-400"
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
          class="rf-input w-72 !border-transparent !bg-brand-50/60 !pl-10 placeholder:text-slate-400"
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

      <span
        v-if="activeView === 'vehicles' && exportError"
        class="text-xs font-semibold text-rose-600"
      >
        {{ exportError }}
      </span>

      <button
        v-if="activeView === 'vehicles'"
        type="button"
        class="rf-btn-secondary"
        :disabled="exportingExcel || loading || !filteredVehicles.length"
        :title="filteredVehicles.length ? 'Listelenen araçları Excel olarak indir' : 'İndirilecek araç yok'"
        @click="exportFleetExcel"
      >
        <span
          v-if="exportingExcel"
          class="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600"
        ></span>
        <svg v-else class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        {{ exportingExcel ? 'Hazırlanıyor...' : "Excel'e Aktar" }}
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
        v-if="activeView === 'rentals'"
        type="button"
        class="rf-btn-primary"
        @click="showRentalModal = true"
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Kiralama Yap
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

      <!-- Kiralamalar -->
      <RentalManager v-if="activeView === 'rentals'" />

      <!-- Krediler -->
      <LoansManager v-if="activeView === 'loans'" />

      <!-- Kredi Detayı -->
      <LoanDetailPage
        v-if="activeView === 'loan-detail'"
        :loan="loanStore.loanDetail"
        @close="ui.closeLoanDetail()"
      />

      <!-- Araç Detayı -->
      <VehicleDetailPage
        v-if="activeView === 'vehicle-detail'"
        :vehicle="detailVehicle"
        @close="ui.closeVehicleDetail()"
        @edit="openEditVehicle"
      />

      <!-- Sürücü Detayı -->
      <DriverDetailPage
        v-if="activeView === 'driver-detail'"
        :driver="detailDriver"
        :rental-history="detailDriverRentals"
        @close="closeDriverDetail"
        @go-rental="onGoRental"
        @rented="onDriverRented"
      />

      <!-- Sürücüler -->
      <div v-if="activeView === 'drivers'" class="space-y-6">
        <RentalWorkflowProgress
          v-if="readyForDriverPick"
          class="mb-4"
          @cancel="quickRentError = ''"
        >
          <p class="mt-2 text-sm text-slate-600">
            Müşteri fiyatı kabul etti. Kayıtlı müşteriyi listeden seçip
            <strong>Otomatik Kiralama Yap</strong>'a basın. İlk kez gelen müşteri için sağ üstten
            <strong>Sürücü Ekle</strong> kullanın.
          </p>
          <p v-if="workflow.vehicleLabel" class="mt-2 text-xs font-semibold text-brand-700">
            Araç: {{ workflow.vehicleLabel }} · {{ workflow.agreedPrice }} ₺
            <span v-if="workflow.pickupDate && workflow.dropoffDate">
              · {{ workflow.pickupDate }} → {{ workflow.dropoffDate }}
            </span>
          </p>
          <p v-if="quickRentError" class="mt-2 text-sm text-rose-700">{{ quickRentError }}</p>
        </RentalWorkflowProgress>

        <div v-if="driverStore.loading && !driverStore.drivers.length" class="grid place-items-center py-16">
          <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
        </div>
        <div v-else-if="driverStore.error" class="text-center text-red-600">Sürücü listesi yüklenemedi.</div>
        <div v-else>
          <div class="mb-4">
            <span class="rf-capsule !py-1.5 text-sm text-slate-600">
              <span class="font-black text-slate-900">{{ filteredDrivers.length }}</span> sürücü
            </span>
          </div>
          <div v-if="filteredDrivers.length" class="rf-glass-strong overflow-x-auto rounded-3xl">
            <table class="w-full min-w-[880px] text-left text-sm">
              <thead>
                <tr class="border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
                  <th class="py-3 pl-4 pr-3">Sürücü</th>
                  <th class="py-3 pr-3">Şehir</th>
                  <th class="py-3 pr-3">Ehliyet</th>
                  <th class="py-3 pr-3 text-center">Kiralama</th>
                  <th class="py-3 pr-3">Risk</th>
                  <th class="py-3 pr-3">Aktif Kiralama</th>
                  <th class="py-3 pr-4"></th>
                </tr>
              </thead>
              <tbody>
                <DriverListRow
                  v-for="driver in filteredDrivers"
                  :key="driver.id"
                  :driver="driver"
                  @select="openDriverDetail"
                  @auto-rent="quickAutoRent"
                />
              </tbody>
            </table>
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

      <!-- Araçlar -->
      <template v-if="activeView === 'vehicles'">
        <div class="relative mb-5 flex items-center justify-center">
          <div class="flex flex-wrap items-center justify-center gap-2">
            <button
              v-for="f in statusFilters"
              :key="f.id"
              type="button"
              class="rf-pill-filter cursor-pointer"
              :class="statusFilter === f.id ? 'rf-pill-filter--active' : 'rf-pill-filter--idle'"
              @click="statusFilter = f.id"
            >
              {{ f.label }}
            </button>
          </div>
          <span class="rf-capsule !py-1.5 absolute right-0 hidden text-sm text-slate-600 sm:inline-flex">
            <span class="font-black text-slate-900">{{ filteredVehicles.length }}</span>&nbsp;araç
          </span>
        </div>

        <div v-if="filteredVehicles.length" class="rf-glass-strong overflow-x-auto rounded-3xl">
          <table class="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr class="border-b border-slate-200 text-xs font-bold uppercase tracking-wider text-slate-500">
                <th class="py-3 pl-4 pr-3">Araç</th>
                <th class="py-3 pr-3">Marka / Model</th>
                <th class="py-3 pr-3">Sınıf</th>
                <th class="py-3 pr-3">Durum</th>
                <th class="py-3 pr-3">Kilometre</th>
                <th class="py-3 pr-4"></th>
              </tr>
            </thead>
            <tbody>
              <VehicleListRow
                v-for="vehicle in filteredVehicles"
                :key="vehicle.id"
                :vehicle="vehicle"
                @select="openDetail"
              />
            </tbody>
          </table>
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

  <VehicleFormModal
    v-if="showVehicleForm"
    :edit-vehicle="editVehicle"
    :edit-profile="editProfile"
    :edit-policies="editPolicies"
    :edit-registration-detail="editRegistrationDetail"
    @close="showVehicleForm = false"
    @saved="onVehicleSaved"
  />

  <DriverFormModal
    v-if="showDriverForm"
    @close="showDriverForm = false"
    @saved="onDriverSaved"
  />

  <ManualRentalModal
    v-if="showRentalModal"
    @close="showRentalModal = false"
    @created="onRentalCreated"
  />
</template>
