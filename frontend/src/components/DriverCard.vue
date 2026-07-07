<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'

const props = defineProps({
  driver: { type: Object, required: true },
})

const emit = defineEmits(['select', 'auto-reserve'])

const workflow = useRentalWorkflowStore()
const { readyForDriverPick } = storeToRefs(workflow)

const riskScore = computed(() => props.driver.risk_skoru ?? null)

const riskBadgeClass = computed(() => {
  const value = riskScore.value
  if (value === null) return 'bg-white/40 text-slate-400'
  if (value <= 30) return 'bg-emerald-100/80 text-emerald-700 ring-emerald-300/50'
  if (value <= 60) return 'bg-amber-100/80 text-amber-700 ring-amber-300/50'
  return 'bg-red-100/80 text-red-700 ring-red-300/50'
})

const rental = computed(() => props.driver.aktif_kiralama)
const canQuickReserve = computed(() =>
  readyForDriverPick.value && !rental.value && !props.driver.is_blacklisted,
)
const kmFmt = new Intl.NumberFormat('tr-TR')
</script>

<template>
  <article
    role="button"
    tabindex="0"
    class="group rf-glass rf-interactive flex cursor-pointer flex-col rounded-3xl p-5 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:ring-offset-2"
    @click="emit('select', driver)"
    @keydown.enter="emit('select', driver)"
    @keydown.space.prevent="emit('select', driver)"
  >
    <div class="flex items-start justify-between gap-3">
      <div>
        <h3 class="text-xl font-black tracking-tight text-slate-900">{{ driver.ad_soyad }}</h3>
        <p class="mt-0.5 text-sm text-slate-500/80">{{ driver.yas }} yaş · {{ driver.cinsiyet }}</p>
      </div>
      <span
        class="inline-flex flex-col items-center rounded-full px-3 py-1 text-xs font-black ring-1 backdrop-blur-sm"
        :class="riskBadgeClass"
        title="Risk Skoru"
      >
        <span class="text-[9px] font-bold uppercase tracking-wider opacity-70">Risk</span>
        {{ riskScore !== null ? riskScore : '··' }}
      </span>
    </div>

    <dl class="mt-5 space-y-2 border-t border-white/30 pt-4 text-sm">
      <div class="flex justify-between gap-2">
        <dt class="text-slate-500/80">Ehliyet</dt>
        <dd class="text-right font-bold text-slate-800">{{ driver.license_class }} · {{ driver.license_number }}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-slate-500/80">Şehir</dt>
        <dd class="font-bold text-slate-800">{{ driver.city }}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-slate-500/80">Kiralama</dt>
        <dd class="font-bold text-slate-800">{{ driver.toplam_kiralama }}</dd>
      </div>
      <div v-if="driver.risk_seviye_label && driver.risk_seviye_label !== '—'" class="flex justify-between">
        <dt class="text-slate-500/80">Risk seviyesi</dt>
        <dd class="font-bold text-slate-800">{{ driver.risk_seviye_label }}</dd>
      </div>
    </dl>

    <button
      v-if="canQuickReserve"
      type="button"
      class="rf-btn-primary mt-4 w-full text-sm"
      @click.stop="emit('auto-reserve', driver)"
    >
      Otomatik Rezervasyon Yap
    </button>

    <div
      v-else-if="rental"
      class="mt-4 rounded-2xl border border-white/40 bg-white/35 px-4 py-3 text-sm backdrop-blur-sm"
    >
      <p class="text-[10px] font-bold uppercase tracking-widest text-brand-600">Aktif Kiralama</p>
      <p class="mt-1 font-black text-slate-900">{{ rental.plaka }}</p>
      <p class="text-sm text-slate-600/90">{{ rental.marka_model_sinif || rental.marka_model }}</p>
      <p class="text-xs text-slate-500/80">{{ kmFmt.format(rental.guncel_km) }} km</p>
    </div>
    <div v-else class="mt-4 rounded-2xl border border-dashed border-white/40 px-3 py-2.5 text-center text-xs text-slate-400">
      Aktif kiralama yok
    </div>

    <span
      v-if="driver.is_blacklisted"
      class="mt-3 inline-flex w-fit items-center rounded-full bg-red-500/15 px-3 py-1 text-xs font-bold text-red-600 ring-1 ring-red-300/40"
    >
      Kara Liste
    </span>

    <p class="mt-3 flex items-center justify-end gap-1 text-sm font-bold text-brand-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
      Profili gör →
    </p>
  </article>
</template>
