<script setup>
// Maliyet dökümü + satır içi simülasyon (kompakt).
import { computed, reactive, ref, watch } from 'vue'
import { formatTL } from '../../utils/format.js'
import {
  computeCostCard,
  seedSimulationFromDecision,
  simulationToVehiclePatch,
} from '../../utils/rentalEconomics.js'
import { useFinanceStore } from '../../stores/financeStore.js'

const props = defineProps({
  vehicleId: { type: Number, default: null },
  decision: { type: Object, default: null },
  rentalDays: { type: Number, default: 1 },
  dateBaslangic: { type: String, default: null },
  dateBitis: { type: String, default: null },
})

const emit = defineEmits(['edit-vehicle', 'applied'])

const finance = useFinanceStore()
const saving = ref(false)
const editMode = ref(false)

const sim = reactive({
  purchase_price: 0,
  rental_prep: 0,
  annual_kasko: 0,
  annual_traffic: 0,
  annual_insurance: 0,
  annual_mtv: 0,
  annual_inspection: 0,
  monthly_maintenance: 0,
  rental_days: 1,
})

function loadSeed() {
  const seed = seedSimulationFromDecision(props.decision, props.rentalDays)
  if (!seed) return
  Object.assign(sim, seed)
}

watch(() => [props.decision, props.rentalDays], loadSeed, { immediate: true })

const hasCost = computed(() => props.decision?.maliyet_karti_var === true)
const tahminler = computed(() => props.decision?.tahmini_alanlar ?? [])
const baseline = computed(() => props.decision?.ozet ?? {})
const preview = computed(() => (editMode.value ? computeCostCard(sim) : null))

const display = computed(() => {
  if (editMode.value && preview.value) {
    return {
      gunluk: preview.value.daily_cost,
      taban: preview.value.period_floor,
      yillik_yuk: preview.value.annual_burden,
      aylik_isletme: preview.value.monthly_operating,
    }
  }
  return {
    gunluk: baseline.value.gunluk_maliyet,
    taban: baseline.value.minimum_kurtaran_fiyat,
    yillik_yuk: props.decision?.maliyet_dagilimi?.yillik_toplam_yuk,
    aylik_isletme: props.decision?.maliyet_dagilimi?.aylik_isletme,
  }
})

const tabanDelta = computed(() => {
  if (!editMode.value || !preview.value) return null
  return Math.round((preview.value.period_floor - (baseline.value.minimum_kurtaran_fiyat || 0)) * 100) / 100
})

const hasSimChanges = computed(() => {
  const seed = seedSimulationFromDecision(props.decision, props.rentalDays)
  if (!seed) return false
  return (
    sim.purchase_price !== seed.purchase_price
    || sim.rental_prep !== seed.rental_prep
    || sim.annual_kasko !== seed.annual_kasko
    || sim.annual_traffic !== seed.annual_traffic
    || sim.annual_mtv !== seed.annual_mtv
    || sim.annual_inspection !== seed.annual_inspection
    || sim.monthly_maintenance !== seed.monthly_maintenance
  )
})

const rows = computed(() => {
  const d = props.decision?.maliyet_dagilimi
  if (!d) return []
  const useSim = editMode.value
  return [
    { key: 'purchase_price', label: 'Alış fiyatı', value: useSim ? sim.purchase_price : d.alis_fiyati, editable: true, unit: 'TL' },
    { key: 'rental_prep', label: 'Kiraya hazırlık', value: useSim ? sim.rental_prep : d.kiraya_hazirlik, editable: true, unit: 'TL' },
    { key: 'annual_kasko', label: 'Kasko (yıllık)', value: useSim ? sim.annual_kasko : d.yillik_kasko, editable: true, unit: 'TL/yıl' },
    { key: 'annual_traffic', label: 'Trafik sigortası (yıllık)', value: useSim ? sim.annual_traffic : d.yillik_trafik_sigortasi, editable: true, unit: 'TL/yıl' },
    { key: 'annual_mtv', label: 'MTV (yıllık)', value: useSim ? sim.annual_mtv : d.yillik_mtv, editable: true, unit: 'TL/yıl' },
    { key: 'annual_inspection', label: 'Muayene (yıllık)', value: useSim ? sim.annual_inspection : d.yillik_muayene, editable: true, unit: 'TL/yıl' },
    { key: 'monthly_maintenance', label: 'Bakım (aylık)', value: useSim ? sim.monthly_maintenance : d.aylik_bakim, editable: true, unit: 'TL/ay' },
    { key: 'aylik_isletme', label: 'Aylık işletme', value: display.value.aylik_isletme, editable: false, unit: 'TL/ay' },
    { key: 'yillik_yuk', label: 'Yıllık toplam yük', value: display.value.yillik_yuk, editable: false, unit: 'TL/yıl', bold: true },
    { key: 'gunluk', label: 'Günlük maliyet', value: display.value.gunluk, editable: false, unit: 'TL/gün', bold: true },
    { key: 'rental_days', label: 'Kiralama süresi', value: useSim ? sim.rental_days : props.rentalDays, editable: true, unit: 'gün', previewOnly: true },
    { key: 'taban', label: 'Minimum kurtaran fiyat', value: display.value.taban, editable: false, unit: 'TL', highlight: true },
  ]
})

function onRowInput(key, raw) {
  sim[key] = Number(raw) || 0
}

async function saveSim() {
  if (!props.vehicleId || !hasSimChanges.value || saving.value) return
  saving.value = true
  try {
    await finance.updateVehicle(props.vehicleId, simulationToVehiclePatch(sim))
    await finance.fetchPricingDecision(props.vehicleId, {
      force: true,
      baslangic: props.dateBaslangic,
      bitis: props.dateBitis,
    })
    editMode.value = false
    emit('applied')
  } finally {
    saving.value = false
  }
}

function cancelEdit() {
  loadSeed()
  editMode.value = false
}
</script>

<template>
  <div v-if="!hasCost" class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
    {{ decision?.mesaj || 'Maliyet hesaplanamıyor.' }}
    <button type="button" class="ml-2 font-semibold underline" @click="emit('edit-vehicle')">Maliyet gir</button>
  </div>

  <div v-else class="space-y-3">
    <div v-if="tahminler.length" class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
      <span class="font-semibold">{{ tahminler.length }} tahmini alan.</span>
      <button type="button" class="ml-1 underline" @click="emit('edit-vehicle')">Düzelt</button>
    </div>

    <div class="flex items-center justify-between gap-2">
      <h5 class="text-sm font-semibold text-slate-800">Hesaplama dökümü</h5>
      <button
        v-if="!editMode"
        type="button"
        class="text-xs font-medium text-brand-600 hover:text-brand-700"
        @click="editMode = true"
      >
        Değerleri düzenle
      </button>
    </div>

    <div class="overflow-hidden rounded-lg border border-slate-200">
      <table class="w-full text-sm">
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.key"
            class="border-b border-slate-100 last:border-0"
            :class="row.highlight ? 'bg-red-50' : ''"
          >
            <td class="px-3 py-2 text-slate-600">
              {{ row.label }}
              <span v-if="row.previewOnly && editMode" class="ml-1 text-[10px] text-slate-400">önizleme</span>
            </td>
            <td class="px-3 py-2 text-right">
              <input
                v-if="editMode && row.editable"
                :value="row.value"
                type="number"
                class="w-28 rounded border border-slate-200 px-2 py-1 text-right text-sm"
                @input="onRowInput(row.key, $event.target.value)"
              />
              <span v-else-if="row.key === 'rental_days'" class="font-semibold text-slate-800">
                {{ row.value }} gün
              </span>
              <span v-else :class="row.bold || row.highlight ? 'font-bold text-slate-900' : 'text-slate-800'">
                {{ formatTL(row.value) }}
                <span v-if="row.unit && row.unit !== 'TL'" class="text-xs font-normal text-slate-400">
                  /{{ row.unit.replace('TL/', '') }}
                </span>
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-if="editMode && tabanDelta != null && tabanDelta !== 0" class="text-xs text-slate-600">
      Taban farkı:
      <strong :class="tabanDelta > 0 ? 'text-amber-700' : 'text-emerald-700'">
        {{ tabanDelta > 0 ? '+' : '' }}{{ formatTL(tabanDelta) }}
      </strong>
      <span v-if="hasSimChanges"> — kaydetmeden önizleme</span>
    </p>

    <div v-if="editMode" class="flex gap-2">
      <button type="button" class="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-xs font-medium text-slate-600" @click="cancelEdit">
        İptal
      </button>
      <button
        type="button"
        class="flex-1 rounded-lg bg-slate-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-40"
        :disabled="!hasSimChanges || saving"
        @click="saveSim"
      >
        {{ saving ? 'Kaydediliyor…' : 'Kaydet' }}
      </button>
    </div>
  </div>
</template>
