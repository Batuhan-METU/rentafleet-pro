<script setup>
// Öngörücü Bakım Merkezi (Day 12).
// Servise ihtiyacı olan araçları listeler; her araç için bakım limitine ne
// kadar yaklaştığını renkli bir ilerleme çubuğuyla gösterir ve agresif sürüşe
// göre Türkçe yıpranma rozeti basar. Veri store.maintenanceAlerts'ten gelir.
import { computed, onMounted } from 'vue'
import { useVehicleStore } from '../stores/vehicleStore.js'

const store = useVehicleStore()

onMounted(() => store.fetchMaintenanceAlerts())

const alerts = computed(() => store.maintenanceAlerts)
const loading = computed(() => store.maintenanceLoading && !alerts.value.length)
const criticalCount = computed(() => alerts.value.filter((a) => a.durum === 'ACIL_KIRMIZI').length)

const kmFmt = new Intl.NumberFormat('tr-TR')
const formatKm = (km) => `${kmFmt.format(km)} km`

function barColor(status) {
  return status === 'ACIL_KIRMIZI' ? 'bg-red-500' : 'bg-amber-500'
}

function statusPill(status) {
  return status === 'ACIL_KIRMIZI'
    ? { label: 'ACİL', cls: 'bg-red-100 text-red-700 ring-red-600/20' }
    : { label: 'YAKLAŞIYOR', cls: 'bg-amber-100 text-amber-700 ring-amber-600/20' }
}
</script>

<template>
  <div class="space-y-4">
    <!-- Özet şerit -->
    <div class="flex flex-wrap items-center gap-2">
      <div class="rf-capsule !py-2">
        <span class="text-sm text-slate-500/80">Bakım bekleyen:</span>
        <span class="ml-1 text-sm font-black text-slate-900">{{ alerts.length }}</span>
      </div>
      <div class="rf-capsule !py-2" :class="criticalCount ? 'ring-1 ring-red-300/40' : ''">
        <span class="text-sm text-slate-500/80">Acil:</span>
        <span class="ml-1 text-sm font-black" :class="criticalCount ? 'text-red-600' : 'text-slate-900'">{{ criticalCount }}</span>
      </div>
      <button
        type="button"
        class="rf-btn-primary ml-auto !py-2"
        :disabled="store.maintenanceLoading"
        @click="store.fetchMaintenanceAlerts()"
      >
        <svg class="h-4 w-4" :class="{ 'animate-spin': store.maintenanceLoading }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Yenile
      </button>
    </div>

    <!-- Yükleniyor -->
    <div v-if="loading" class="rf-glass grid place-items-center rounded-3xl p-16">
      <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
      <p class="mt-3 text-sm text-slate-500">Bakım analizleri hesaplanıyor...</p>
    </div>

    <!-- Boş durum -->
    <div v-else-if="!alerts.length" class="rf-glass grid place-items-center rounded-3xl p-16 text-center">
      <span class="rf-icon-ring !h-14 !w-14 text-emerald-600">✓</span>
      <p class="mt-4 text-base font-semibold text-slate-700">Tüm araçlar bakım açısından iyi durumda</p>
      <p class="mt-1 text-sm text-slate-500">Şu anda servis gerektiren araç bulunmuyor.</p>
    </div>

    <!-- Liste -->
    <div v-else class="space-y-3">
      <div
        v-for="v in alerts"
        :key="v.id"
        class="rf-glass rf-interactive rounded-3xl p-5"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="flex items-center gap-2">
              <span class="text-base font-bold text-slate-900">{{ v.plaka }}</span>
              <span
                class="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset"
                :class="statusPill(v.durum).cls"
              >
                {{ statusPill(v.durum).label }}
              </span>
            </div>
            <p class="text-sm text-slate-500">{{ v.marka_model }}</p>
          </div>

          <!-- Yıpranma rozeti -->
          <span
            class="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-semibold"
            :class="v.agresif_surus ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-600'"
          >
            <span class="h-1.5 w-1.5 rounded-full" :class="v.agresif_surus ? 'bg-red-500' : 'bg-slate-400'"></span>
            {{ v.agresif_surus ? 'Kritik Yıpranma (Agresif Sürüş)' : 'Normal Aşınma' }}
          </span>
        </div>

        <!-- İlerleme çubuğu -->
        <div class="mt-4">
          <div class="mb-1 flex items-center justify-between text-xs text-slate-500">
            <span>{{ formatKm(v.guncel_km) }}</span>
            <span>Hedef: {{ formatKm(v.hedef_km) }}</span>
          </div>
          <div class="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div class="h-full rounded-full transition-all" :class="barColor(v.durum)" :style="{ width: v.ilerleme_yuzdesi + '%' }"></div>
          </div>
          <div class="mt-2 flex items-center justify-between text-sm">
            <span class="text-slate-500">Sürücü skoru: <b class="text-slate-700">{{ v.surus_skoru }}</b></span>
            <span
              class="font-semibold"
              :class="v.durum === 'ACIL_KIRMIZI' ? 'text-red-600' : 'text-amber-600'"
            >
              {{ v.kalan_km <= 0 ? 'Bakım zamanı geçti!' : `${formatKm(v.kalan_km)} kaldı` }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
