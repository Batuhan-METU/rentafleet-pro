<script setup>
// Öngörücü Bakım Merkezi.
// Gerçek kural: son bakımdan itibaren 10.000-15.000 km ARASI veya en geç
// 12 ay geçince bakım şart — hangisi önce dolarsa. Backend artık TÜM
// araçları (sağlıklı dahil) tek uçtan döner; bu bileşen store.vehicles
// gibi alakasız bir kaynağa bel bağlamaz.
// Üstteki üç özet kutusu aynı zamanda birer filtre: Sağlıklı/Bakım
// Bekleyen/Acil'e tıklamak altındaki listeyi o kümeye daraltır.
import { computed, onMounted, ref } from 'vue'
import { useVehicleMaintenanceStore } from '../stores/vehicleMaintenanceStore.js'
import { downloadExcelReport } from '../utils/exportExcel.js'
import { formatKm } from '../utils/format.js'
import MaintenanceVehicleCard from './MaintenanceVehicleCard.vue'

const store = useVehicleMaintenanceStore()

onMounted(() => store.fetchMaintenanceAlerts())

const allVehicles = computed(() => store.maintenanceAlerts)
const loading = computed(() => store.maintenanceLoading && !allVehicles.value.length)

// Üç durum birbirini DIŞLAR (bir araç yalnızca birinde görünür) — önceden
// "Bakım Bekleyen" WARNING+CRITICAL'in TOPLAMINI gösteriyordu, bu yüzden
// "Acil" listesiyle görünürde çakışıyordu.
const healthyVehicles = computed(() => allVehicles.value.filter((v) => v.status === 'HEALTHY'))
const pendingVehicles = computed(() => allVehicles.value.filter((v) => v.status === 'WARNING'))
const criticalVehicles = computed(() => allVehicles.value.filter((v) => v.status === 'CRITICAL'))
const criticalCount = computed(() => store.maintenanceCounts.critical)
const healthyCount = computed(() => store.maintenanceCounts.healthy)
const pendingCount = computed(() => store.maintenanceCounts.warning)

// 'PENDING' = yalnızca yaklaşan (varsayılan), 'URGENT' = yalnızca acil, 'HEALTHY' = sağlıklı araçlar.
const activeFilter = ref('PENDING')

const filters = computed(() => [
  { id: 'HEALTHY', label: 'Sağlıklı', count: healthyCount.value, tone: 'emerald' },
  { id: 'PENDING', label: 'Bakım Bekleyen', count: pendingCount.value, tone: 'amber' },
  { id: 'URGENT', label: 'Acil', count: criticalCount.value, tone: 'red', pulse: true },
])

const displayedAlerts = computed(() => {
  if (activeFilter.value === 'URGENT') return criticalVehicles.value
  if (activeFilter.value === 'HEALTHY') return []
  return pendingVehicles.value
})

// "Acil" listesi, KRİTİK sebebe göre 3 dışlayıcı sütuna bölünür — hem km
// hem süre dolmuş, yalnızca km dolmuş, yalnızca süre dolmuş. Her acil araç
// bu üçünden TAM BİRİNE düşer (km_status/date_status zaten CRITICAL'ı
// belirliyor).
const urgentColumns = computed(() => {
  const both = []
  const kmOnly = []
  const dateOnly = []
  for (const v of criticalVehicles.value) {
    const kmDone = v.km_status === 'CRITICAL'
    const dateDone = v.date_status === 'CRITICAL'
    if (kmDone && dateDone) both.push(v)
    else if (kmDone) kmOnly.push(v)
    else dateOnly.push(v)
  }
  return [
    { id: 'both', label: 'Hem KM Hem Süre Dolmuş', vehicles: both },
    { id: 'km', label: 'KM Sınırı Dolmuş', vehicles: kmOnly },
    { id: 'date', label: 'Süre Sınırı Dolmuş', vehicles: dateOnly },
  ]
})

// --- Toplu Excel dışa aktarma ------------------------------------------
// Seçili özet kutusu (Sağlıklı / Bakım Bekleyen / Acil) backend'e filtre
// olarak iletilir: Excel her zaman ekranda listelenen kümeyi indirir.
const exportingExcel = ref(false)
const exportError = ref('')
let exportErrorTimer = null

const exportableCount = computed(() =>
  activeFilter.value === 'HEALTHY' ? healthyVehicles.value.length : displayedAlerts.value.length,
)

async function exportMaintenanceExcel() {
  if (exportingExcel.value) return
  exportingExcel.value = true
  exportError.value = ''
  try {
    await downloadExcelReport('vehicles/maintenance-alerts/export/', {
      params: { status_filter: activeFilter.value },
      filenamePrefix: 'Bakim_Raporu',
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

const tileClass = {
  emerald: 'bg-emerald-50',
  amber: 'bg-amber-50',
  red: 'bg-red-50',
}

const tileTextClass = {
  emerald: 'text-emerald-700',
  amber: 'text-amber-700',
  red: 'text-red-700',
}
</script>

<template>
  <div class="space-y-4">
    <!-- Özet şerit / filtreler -->
    <div class="rf-glass-strong flex flex-wrap items-center gap-2 rounded-3xl p-3">
      <button
        v-for="f in filters"
        :key="f.id"
        type="button"
        class="cursor-pointer rounded-2xl px-4 py-2 text-left transition-all duration-200"
        :class="[
          tileClass[f.tone],
          activeFilter === f.id ? 'ring-2 ring-offset-1' : 'hover:-translate-y-0.5 hover:shadow-md',
          activeFilter === f.id && f.tone === 'emerald' ? 'ring-emerald-400' : '',
          activeFilter === f.id && f.tone === 'amber' ? 'ring-amber-400' : '',
          activeFilter === f.id && f.tone === 'red' ? 'ring-red-400' : '',
        ]"
        @click="activeFilter = f.id"
      >
        <p class="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wide" :class="`${tileTextClass[f.tone]}/70`">
          <span v-if="f.pulse && f.count" class="h-1.5 w-1.5 rounded-full bg-red-600 animate-pulse" />
          {{ f.label }}
        </p>
        <p class="text-xl font-black leading-tight" :class="tileTextClass[f.tone]">{{ f.count }}</p>
      </button>

      <div class="ml-auto flex items-center gap-3 pr-1">
        <span v-if="exportError" class="text-xs font-semibold text-rose-600">
          {{ exportError }}
        </span>
        <button
          type="button"
          class="rf-btn-secondary !px-4 !py-2 !text-xs"
          :disabled="exportingExcel || loading || !exportableCount"
          :title="exportableCount ? 'Listelenen araçları Excel olarak indir' : 'İndirilecek kayıt yok'"
          @click="exportMaintenanceExcel"
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

    <!-- Yükleniyor -->
    <div v-if="loading" class="rf-glass grid place-items-center rounded-3xl p-16">
      <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
      <p class="mt-3 text-sm text-slate-500">Bakım analizleri hesaplanıyor...</p>
    </div>

    <!-- Sağlıklı araçlar -->
    <div v-else-if="activeFilter === 'HEALTHY'">
      <div v-if="healthyVehicles.length" class="space-y-2">
        <div
          v-for="v in healthyVehicles"
          :key="v.id"
          class="rf-glass flex items-center justify-between rounded-2xl px-5 py-3.5"
        >
          <div class="flex items-center gap-3">
            <span class="rf-icon-ring !h-9 !w-9 !text-sm text-emerald-600">✓</span>
            <div>
              <p class="font-bold text-slate-900">{{ v.plate_number }}</p>
              <p class="text-xs text-slate-500">{{ v.brand_model }}</p>
            </div>
          </div>
          <span class="text-sm font-semibold text-slate-600">{{ formatKm(v.current_km) }}</span>
        </div>
      </div>
      <div v-else class="rf-glass grid place-items-center rounded-3xl p-16 text-center">
        <p class="text-sm text-slate-500">Sağlıklı araç bulunamadı.</p>
      </div>
    </div>

    <!-- Boş durum -->
    <div v-else-if="!displayedAlerts.length" class="rf-glass grid place-items-center rounded-3xl p-16 text-center">
      <span class="rf-icon-ring !h-14 !w-14 text-emerald-600">✓</span>
      <p class="mt-4 text-base font-semibold text-slate-700">Tüm araçlar bakım açısından iyi durumda</p>
      <p class="mt-1 text-sm text-slate-500">Şu anda servis gerektiren araç bulunmuyor.</p>
    </div>

    <!-- Acil: kritik SEBEBE göre 3 dışlayıcı sütun -->
    <div v-else-if="activeFilter === 'URGENT'" class="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div v-for="col in urgentColumns" :key="col.id">
        <p class="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-red-700/70">
          {{ col.label }}
          <span class="rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] text-red-700">{{ col.vehicles.length }}</span>
        </p>
        <div v-if="col.vehicles.length" class="space-y-3">
          <MaintenanceVehicleCard v-for="v in col.vehicles" :key="v.id" :vehicle="v" />
        </div>
        <div v-else class="rf-glass grid place-items-center rounded-2xl p-6 text-center">
          <p class="text-xs text-slate-400">Bu grupta araç yok.</p>
        </div>
      </div>
    </div>

    <!-- Bakım Bekleyen -->
    <div v-else class="space-y-3">
      <MaintenanceVehicleCard v-for="v in displayedAlerts" :key="v.id" :vehicle="v" />
    </div>
  </div>
</template>
