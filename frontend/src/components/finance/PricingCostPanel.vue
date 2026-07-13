<script setup>
import { computed, ref, watch } from 'vue'
import { formatTL } from '../../utils/format.js'
import { useFinanceStore } from '../../stores/financeStore.js'
import PricingDecisionWaterfall from './PricingDecisionWaterfall.vue'
import PricingOfferAnalysis from './PricingOfferAnalysis.vue'

const props = defineProps({
  vehicleId: { type: Number, default: null },
  decision: { type: Object, default: null },
  quote: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  offerLoading: { type: Boolean, default: false },
  marketAverage: { type: Number, default: null },
  rentalDays: { type: Number, default: 1 },
  dateBaslangic: { type: String, default: null },
  dateBitis: { type: String, default: null },
  datesReady: { type: Boolean, default: false },
  windowLabel: { type: String, default: '' },
})

const emit = defineEmits(['edit-vehicle', 'offer-accepted', 'simulation-applied'])

const finance = useFinanceStore()
const offerInput = ref('')
let offerDebounceTimer = null

const quoteData = computed(() => props.quote ?? props.decision?.kiralama ?? null)
const hasCost = computed(() => props.decision?.maliyet_karti_var === true)
const showLoading = computed(() => props.loading && !hasCost.value)

const tabanFiyat = computed(
  () => props.decision?.ozet?.minimum_kurtaran_fiyat ?? quoteData.value?.donem_taban_fiyat,
)
const gunlukMaliyet = computed(
  () => props.decision?.ozet?.gunluk_maliyet ?? quoteData.value?.gunluk_maliyet,
)
const offerAnalysis = computed(() => props.decision?.mudur_teklifi ?? null)

const marketPeriod = computed(() => {
  if (props.decision?.piyasa?.donem_toplam != null) return props.decision.piyasa.donem_toplam
  if (props.marketAverage && props.rentalDays) return Math.round(props.marketAverage * props.rentalDays)
  return null
})

const canEnterPrice = computed(() => props.datesReady && hasCost.value && props.rentalDays >= 1)

const inputBorderClass = computed(() => {
  const a = offerAnalysis.value
  if (!a) return 'border-slate-200'
  if (a.durum === 'zarar') return 'border-red-400 ring-1 ring-red-200'
  if (a.durum === 'kar') return 'border-emerald-400 ring-1 ring-emerald-200'
  return 'border-amber-400 ring-1 ring-amber-200'
})

function parseOffer(raw) {
  const cleaned = String(raw).replace(/\s/g, '').replace(/\./g, '').replace(',', '.')
  const n = Number(cleaned)
  return Number.isNaN(n) || n <= 0 ? null : n
}

const validOffer = computed(() => parseOffer(offerInput.value) != null)

function acceptOffer() {
  const offered = parseOffer(offerInput.value)
  if (offered == null) return
  emit('offer-accepted', offered)
}

function refreshOfferPreview(teklif) {
  if (!props.vehicleId || teklif == null) return
  void finance.fetchPricingDecision(props.vehicleId, {
    force: true,
    baslangic: props.dateBaslangic,
    bitis: props.dateBitis,
    teklif,
  })
}

watch(offerInput, (raw) => {
  if (!canEnterPrice.value) return
  clearTimeout(offerDebounceTimer)
  const teklif = parseOffer(raw)
  if (teklif == null) {
    if (props.vehicleId && props.decision?.mudur_teklifi) {
      void finance.fetchPricingDecision(props.vehicleId, {
        force: true,
        baslangic: props.dateBaslangic,
        bitis: props.dateBitis,
      })
    }
    return
  }
  offerDebounceTimer = setTimeout(() => refreshOfferPreview(teklif), 450)
})

watch(() => [props.vehicleId, props.dateBaslangic, props.dateBitis], () => {
  offerInput.value = ''
})
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
    <!-- Özet şerit -->
    <div class="border-b border-slate-100 px-4 py-4">
      <div v-if="showLoading" class="py-6 text-center text-sm text-slate-400">Hesaplanıyor…</div>

      <div v-else-if="!hasCost" class="space-y-3">
        <p class="text-sm text-slate-600">Bu araç için maliyet bilgisi eksik.</p>
        <button type="button" class="text-sm font-medium text-brand-600" @click="emit('edit-vehicle')">
          Maliyet bilgilerini gir →
        </button>
      </div>

      <div v-else class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div>
          <p class="text-xs text-slate-500">Minimum taban</p>
          <p class="text-lg font-bold text-red-600">{{ formatTL(tabanFiyat) }}</p>
        </div>
        <div>
          <p class="text-xs text-slate-500">Günlük maliyet</p>
          <p class="text-lg font-semibold text-slate-800">{{ formatTL(gunlukMaliyet) }}</p>
        </div>
        <div>
          <p class="text-xs text-slate-500">Süre</p>
          <p class="text-lg font-semibold text-slate-800">{{ rentalDays }} gün</p>
        </div>
        <div>
          <p class="text-xs text-slate-500">Piyasa (dönem)</p>
          <p class="text-lg font-semibold text-emerald-700">
            {{ marketPeriod != null ? formatTL(marketPeriod) : '—' }}
          </p>
        </div>
      </div>
    </div>

    <!-- Fiyat girişi — tarihler hazır olunca -->
    <div class="border-b border-slate-100 px-4 py-4">
      <template v-if="!datesReady">
        <p class="text-sm text-slate-500">
          Fiyat girmek için önce <strong>alış ve dönüş tarihlerini</strong> seçip hesaplamayı başlatın.
        </p>
      </template>
      <template v-else-if="!hasCost" />
      <template v-else>
        <p class="mb-1 text-xs text-slate-500">{{ windowLabel }}</p>
        <label class="block">
          <span class="text-sm font-medium text-slate-700">
            Toplam kiralama bedeli
            <span class="font-normal text-slate-400">({{ rentalDays }} gün)</span>
          </span>
          <input
            v-model="offerInput"
            type="text"
            inputmode="decimal"
            autocomplete="off"
            class="mt-1.5 w-full rounded-lg border px-3 py-2.5 text-lg font-semibold text-slate-900 transition"
            :class="inputBorderClass"
            :placeholder="marketPeriod ? String(Math.round(marketPeriod)) : (tabanFiyat ? String(Math.round(tabanFiyat * 1.1)) : '')"
          />
        </label>

        <PricingOfferAnalysis
          v-if="offerAnalysis"
          class="mt-3"
          :analysis="offerAnalysis"
          :loading="offerLoading"
          :rental-days="rentalDays"
          compact
        />

        <button
          v-if="validOffer && offerAnalysis && !offerAnalysis.taban_altinda"
          type="button"
          class="mt-3 w-full rounded-lg bg-slate-900 py-2.5 text-sm font-medium text-white"
          @click="acceptOffer"
        >
          Rezervasyona devam et
        </button>
        <p
          v-else-if="validOffer && offerAnalysis?.taban_altinda"
          class="mt-3 rounded-lg bg-red-50 px-3 py-2 text-center text-xs text-red-700"
        >
          Tabanın altında — fiyatı yükseltin.
        </p>
      </template>
    </div>

    <!-- Döküm + simülasyon -->
    <div class="flex-1 overflow-y-auto px-4 py-4">
      <PricingDecisionWaterfall
        v-if="hasCost"
        :vehicle-id="vehicleId"
        :decision="decision"
        :rental-days="rentalDays"
        :date-baslangic="dateBaslangic"
        :date-bitis="dateBitis"
        @edit-vehicle="emit('edit-vehicle')"
        @applied="emit('simulation-applied')"
      />
    </div>
  </div>
</template>
