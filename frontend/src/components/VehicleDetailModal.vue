<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { useAuthStore } from '../stores/authStore.js'
import { useFinanceStore } from '../stores/financeStore.js'
import { formatTL } from '../utils/format.js'
import PricingHistoryPerformance from './finance/PricingHistoryPerformance.vue'

const props = defineProps({
  vehicle: { type: Object, required: true },
})
const emit = defineEmits(['close', 'edit'])

const auth = useAuthStore()
const finance = useFinanceStore()
const profitLoading = ref(false)
const profitDecision = ref(null)

const gecmisPerformans = computed(() => profitDecision.value?.gecmis_performans ?? null)
const birikenKar = computed(() => profitDecision.value?.biriken_kar ?? 0)
const maliyet = computed(() => profitDecision.value?.ozet ?? props.vehicle.maliyet_analizi ?? null)

const FUEL = { GASOLINE: 'Benzin', DIESEL: 'Dizel', LPG: 'LPG', HYBRID: 'Hibrit', ELECTRIC: 'Elektrik' }
const TRANS = { MANUAL: 'Manuel', AUTOMATIC: 'Otomatik', SEMI_AUTOMATIC: 'Yarı otomatik' }
const BODY = {
  SEDAN: 'Sedan', HATCHBACK: 'Hatchback', STATION_WAGON: 'Station', SUV: 'SUV',
  CROSSOVER: 'Crossover', MINIVAN: 'Minivan', PICKUP: 'Pickup', VAN: 'Panelvan', COUPE: 'Coupe',
}

const infoRows = computed(() => {
  const v = props.vehicle
  return [
    { label: 'Durum', value: v.statusInfo?.label ?? v.status_display ?? v.status },
    { label: 'Model yılı', value: v.production_year },
    { label: 'Kilometre', value: v.current_km != null ? `${Number(v.current_km).toLocaleString('tr-TR')} km` : '—' },
    { label: 'Yakıt', value: FUEL[v.fuel_type] ?? v.fuel_type ?? '—' },
    { label: 'Şanzıman', value: TRANS[v.transmission] ?? v.transmission ?? '—' },
    { label: 'Kasa', value: BODY[v.body_type] ?? v.body_type ?? '—' },
    { label: 'Sınıf', value: v.sinif_etiketi ?? '—' },
    { label: 'SIPP', value: v.sipp_code || '—' },
    { label: 'Alış fiyatı', value: v.purchase_price ? formatTL(v.purchase_price) : '—' },
    { label: 'Günlük maliyet', value: maliyet.value?.gunluk_maliyet ? formatTL(maliyet.value.gunluk_maliyet) : '—' },
  ]
})

async function loadProfitSummary() {
  if (!auth.isFleetManager) return
  profitLoading.value = true
  try {
    profitDecision.value = await finance.fetchPricingDecision(props.vehicle.id, { force: true })
  } catch {
    profitDecision.value = null
  } finally {
    profitLoading.value = false
  }
}

function close() {
  emit('close')
}

function onKeydown(event) {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  void loadProfitSummary()
  document.addEventListener('keydown', onKeydown)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="close">
      <div class="absolute inset-0 bg-slate-900/50" />

      <div class="relative z-10 flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-xl bg-white shadow-xl">
        <header class="flex items-start justify-between border-b border-slate-200 px-5 py-4">
          <div>
            <p class="text-lg font-semibold text-slate-900">{{ vehicle.plate_number }}</p>
            <p class="text-sm text-slate-600">{{ vehicle.brand }} {{ vehicle.model }}</p>
            <p v-if="vehicle.package" class="text-xs text-slate-400">{{ vehicle.package }}</p>
          </div>
          <button
            type="button"
            class="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Kapat"
            @click="close"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div class="flex-1 overflow-y-auto px-5 py-4">
          <dl class="divide-y divide-slate-100 rounded-lg border border-slate-200">
            <div
              v-for="row in infoRows"
              :key="row.label"
              class="flex justify-between gap-4 px-4 py-2.5 text-sm"
            >
              <dt class="text-slate-500">{{ row.label }}</dt>
              <dd class="text-right font-medium text-slate-900">{{ row.value }}</dd>
            </div>
          </dl>

          <p v-if="vehicle.sipp_detay" class="mt-3 text-xs text-slate-500">{{ vehicle.sipp_detay }}</p>

          <section v-if="auth.isFleetManager" class="mt-5">
            <h3 class="mb-2 text-sm font-semibold text-slate-800">Kârlılık</h3>
            <div v-if="profitLoading" class="py-4 text-center text-sm text-slate-400">Yükleniyor…</div>
            <PricingHistoryPerformance
              v-else
              :performance="gecmisPerformans"
              :biriken-kar="birikenKar"
            />
          </section>
        </div>

        <footer class="flex gap-2 border-t border-slate-200 px-5 py-3">
          <button
            v-if="auth.isFleetManager"
            type="button"
            class="flex-1 rounded-lg border border-slate-200 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            @click="emit('edit', vehicle)"
          >
            Düzenle
          </button>
          <button
            type="button"
            class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
            @click="close"
          >
            Kapat
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>
