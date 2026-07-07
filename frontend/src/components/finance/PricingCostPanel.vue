<script setup>
// Fiyatlandırma: X günlük kiralama maliyet tabanı + piyasa + müdür teklifi.
import { computed, ref } from 'vue'
import { formatTL } from '../../utils/format.js'

const props = defineProps({
  quote: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  marketAverage: { type: Number, default: null },
  rentalDays: { type: Number, default: 1 },
})

const emit = defineEmits(['edit-vehicle', 'offer-accepted'])

const offerInput = ref('')

const hasCost = computed(() => props.quote?.maliyet_karti_var === true)
const showLoading = computed(() => props.loading && !hasCost.value)
const card = computed(() => props.quote?.maliyet_karti ?? {})
const birikenKar = computed(() => props.quote?.biriken_kar ?? 0)
const kiralamaSayisi = computed(() => props.quote?.biriken_kar_ozeti?.kiralama_sayisi ?? 0)

const marketPeriod = computed(() => {
  if (props.quote?.piyasa_donem_toplam != null) return props.quote.piyasa_donem_toplam
  if (props.marketAverage && props.rentalDays) {
    return Math.round(props.marketAverage * props.rentalDays)
  }
  return null
})

function parseOffer(raw) {
  const cleaned = String(raw).replace(/\s/g, '').replace(/\./g, '').replace(',', '.')
  const n = Number(cleaned)
  return Number.isNaN(n) || n <= 0 ? null : n
}

const profitPreview = computed(() => {
  const offered = parseOffer(offerInput.value)
  if (offered == null || !props.quote?.donem_taban_fiyat) return null
  return Math.round((offered - props.quote.donem_taban_fiyat) * 100) / 100
})

const validOffer = computed(() => parseOffer(offerInput.value) != null)

const totalKarAfterOffer = computed(() => {
  if (profitPreview.value == null) return null
  return Math.round((birikenKar.value + profitPreview.value) * 100) / 100
})

function acceptOffer() {
  const offered = parseOffer(offerInput.value)
  if (offered == null) return
  emit('offer-accepted', offered)
}
</script>

<template>
  <div class="rf-glass-strong overflow-hidden rounded-3xl">
    <div class="border-b border-white/30 bg-white/25 px-5 py-4 backdrop-blur-sm">
      <h4 class="text-sm font-black text-slate-900">Kiralama Fiyatı</h4>
      <p class="text-xs text-slate-500/80">
        {{ rentalDays }} günlük kiralama — 1 yıllık maliyet planına göre taban fiyat
      </p>
    </div>

    <div v-if="showLoading" class="p-8 text-center text-sm text-slate-400">
      <span class="inline-flex items-center gap-2">
        <span class="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-brand-600"></span>
        Hesaplanıyor…
      </span>
    </div>

    <div v-else-if="!hasCost" class="space-y-4 p-5">
      <div class="rf-glass rounded-2xl px-4 py-3 text-sm text-amber-900">
        Bu araç için alış fiyatı ve maliyet bilgisi girilmemiş. Yine de müşteriye fiyat söyleyebilirsiniz.
      </div>
      <button
        type="button"
        class="rf-btn-ghost w-full text-sm"
        @click="emit('edit-vehicle')"
      >
        Maliyet Bilgilerini Gir
      </button>
    </div>

    <div v-if="hasCost" class="space-y-4 p-5">
      <div class="rf-glass rounded-2xl px-4 py-3">
        <p class="text-[11px] font-bold uppercase tracking-wider text-violet-700/90">Şirkete Biriken Kâr</p>
        <p class="mt-1 text-2xl font-bold" :class="birikenKar >= 0 ? 'text-violet-900' : 'text-red-700'">
          {{ formatTL(birikenKar) }}
        </p>
        <p class="mt-1 text-xs text-violet-700">
          {{ kiralamaSayisi }} tamamlanan kiralama
          <span v-if="quote.biriken_kar_ozeti?.kiralanan_gun">
            · {{ quote.biriken_kar_ozeti.kiralanan_gun }} gün kirada
          </span>
        </p>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div class="rf-glass rounded-2xl px-3 py-2.5">
          <p class="text-[11px] font-bold uppercase tracking-wider text-red-600/90">Seni Kurtaran Taban</p>
          <p class="mt-0.5 text-lg font-bold text-red-700">{{ formatTL(quote.donem_taban_fiyat) }}</p>
          <p class="text-[11px] text-red-500">{{ rentalDays }} gün · günlük {{ formatTL(quote.gunluk_maliyet) }}</p>
        </div>
        <div class="rf-glass rounded-2xl px-3 py-2.5">
          <p class="text-[11px] font-bold uppercase tracking-wider text-emerald-700/90">Piyasa (dönem)</p>
          <p class="mt-0.5 text-lg font-bold text-emerald-800">
            {{ marketPeriod != null ? formatTL(marketPeriod) : '—' }}
          </p>
          <p v-if="marketAverage" class="text-[11px] text-emerald-600">
            Günlük ort. {{ formatTL(marketAverage) }}
          </p>
        </div>
      </div>

      <div
        v-if="quote.piyasa_uyarisi"
        class="rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs leading-relaxed text-amber-900"
      >
        {{ quote.piyasa_uyarisi }}
      </div>

      <div class="rf-glass rounded-2xl px-4 py-3 text-xs text-slate-600">
        <p class="mb-2 font-semibold text-slate-700">Maliyet kartı (1 yıl / 365 gün planı)</p>
        <div class="grid grid-cols-2 gap-x-4 gap-y-1">
          <span>Alış fiyatı</span><span class="text-right font-medium">{{ formatTL(card.alis_fiyati) }}</span>
          <span>Kiraya hazırlık</span><span class="text-right font-medium">{{ formatTL(card.kiraya_hazirlik) }}</span>
          <span>Aylık işletme</span><span class="text-right font-medium">{{ formatTL(card.aylik_isletme) }}</span>
          <span class="font-semibold text-slate-800">Yıllık toplam yük</span>
          <span class="text-right font-bold text-slate-800">{{ formatTL(card.yillik_toplam_yuk) }}</span>
        </div>
      </div>
    </div>

    <!-- Fiyat girişi — yükleme bitince veya maliyet yokken de kullanılabilir -->
    <div v-if="!showLoading" class="space-y-4 border-t border-white/30 p-5">
      <div class="rf-glass-strong rounded-2xl p-4 ring-1 ring-brand-300/30">
        <label class="block">
          <span class="mb-1 block text-xs font-bold text-brand-800">
            Müşteriye Söyleyeceğin Toplam Fiyat ({{ rentalDays }} gün)
          </span>
          <input
            v-model="offerInput"
            type="text"
            inputmode="decimal"
            autocomplete="off"
            class="rf-input !text-lg !font-black text-brand-900"
            :placeholder="marketPeriod
              ? String(Math.round(marketPeriod))
              : (quote?.donem_taban_fiyat ? String(Math.round(quote.donem_taban_fiyat * 1.1)) : 'Örn. 4500')"
          />
        </label>
        <p v-if="profitPreview != null" class="mt-3 space-y-1 text-sm">
          <span class="block" :class="profitPreview >= 0 ? 'text-emerald-700' : 'text-red-700'">
            Bu kiralama kârı:
            <strong>{{ profitPreview >= 0 ? '+' : '' }}{{ formatTL(profitPreview) }}</strong>
          </span>
          <span v-if="totalKarAfterOffer != null" class="block font-semibold text-violet-800">
            Toplam biriken kâr (bu kiralama ile):
            <strong>{{ formatTL(totalKarAfterOffer) }}</strong>
          </span>
        </p>
        <p v-else-if="offerInput.trim() && !validOffer" class="mt-2 text-xs text-slate-500">Geçerli bir tutar girin.</p>
        <button
          v-if="validOffer"
          type="button"
          class="rf-btn-primary mt-4 w-full"
          @click="acceptOffer"
        >
          Müşteri Kabul Etti — Sürücü Bilgilerini Al
        </button>
      </div>
    </div>
  </div>
</template>
