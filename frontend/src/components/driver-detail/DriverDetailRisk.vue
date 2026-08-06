<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRentalWorkflowStore } from '../../stores/rentalWorkflowStore.js'
import { formatTL } from '../../utils/format.js'

const props = defineProps({
  driver: { type: Object, required: true },
})

const workflow = useRentalWorkflowStore()
const { agreedPrice } = storeToRefs(workflow)

const risk = computed(() => props.driver?.risk ?? null)

const depositPercent = computed(() => {
  const percent = risk.value?.depozito_orani
  return percent == null ? null : Number(percent)
})

const depositPercentLabel = computed(() =>
  depositPercent.value == null ? null : `%${Math.round(depositPercent.value * 100)}`,
)

// Kiralama fiyatı henüz fiyatlandırma ekranından anlaşılmamışsa yalnızca
// oran gösterilir; anlaşılmışsa (workflow aktifse) o fiyat üzerinden gerçek
// tutar hesaplanır — depozito, aracın fiyatı değil kiralama fiyatı üzerinden alınır.
const estimatedDeposit = computed(() => {
  if (depositPercent.value == null || agreedPrice.value == null) return null
  return depositPercent.value * Number(agreedPrice.value)
})

const riskTone = computed(() => {
  const score = risk.value?.skor
  if (score == null) return { border: 'border-slate-200', text: 'text-slate-400', soft: 'bg-slate-50 text-slate-500' }
  if (score <= 30) return { border: 'border-emerald-500', text: 'text-emerald-600', soft: 'bg-emerald-50 text-emerald-700' }
  if (score <= 60) return { border: 'border-amber-500', text: 'text-amber-600', soft: 'bg-amber-50 text-amber-700' }
  return { border: 'border-red-500', text: 'text-red-600', soft: 'bg-red-50 text-red-700' }
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-4 text-sm font-bold uppercase tracking-wider text-slate-500">Risk Skoru</h3>
    <div v-if="risk" class="flex flex-wrap items-start gap-5">
      <div class="grid h-28 w-28 shrink-0 place-items-center rounded-full border-8" :class="riskTone.border">
        <p class="text-3xl font-extrabold" :class="riskTone.text">{{ risk.skor ?? '—' }}</p>
      </div>
      <div class="min-w-[12rem] flex-1 space-y-2 text-sm">
        <p class="rounded-lg px-3 py-2 font-semibold" :class="riskTone.soft">
          Seviye: {{ risk.seviye_label || '—' }}
        </p>
        <p v-if="depositPercentLabel" class="rounded-lg bg-slate-50 px-3 py-2">
          Depozito oranı: <b>{{ depositPercentLabel }}</b> (kiralama fiyatının)
          <span v-if="estimatedDeposit != null" class="block text-xs text-slate-500">
            Anlaşılan kiralama fiyatı üzerinden: <b>{{ formatTL(estimatedDeposit, { decimals: true }) }}</b>
          </span>
          <span v-else class="block text-xs text-slate-500">
            Tutar, fiyatlandırma ekranında anlaşılan kiralama fiyatı belli olduğunda hesaplanır.
          </span>
        </p>
        <ul v-if="risk.uyarilar?.length" class="list-disc pl-5 text-amber-700">
          <li v-for="(w, i) in risk.uyarilar" :key="i">{{ w }}</li>
        </ul>
        <ul v-if="risk.blokajlar?.length" class="list-disc pl-5 text-rose-700">
          <li v-for="(b, i) in risk.blokajlar" :key="i">{{ b }}</li>
        </ul>
      </div>
    </div>
    <p v-else class="text-sm text-slate-500">Henüz risk değerlendirmesi yapılmamış.</p>
  </section>
</template>
