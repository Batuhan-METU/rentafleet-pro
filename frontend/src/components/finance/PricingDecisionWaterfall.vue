<script setup>
// Maliyet dökümü (salt okunur, gizli/gömülü). Ayrıntılar varsayılan olarak
// katlanmıştır; "Detayları göster" ile açılır. Backend'in ürettiği
// `calculation_steps` dizisi doğrudan render edilir — burada elle alan
// eşleştirmesi YOK, böylece backend formül sırası/adımları değişirse
// frontend otomatik senkron kalır.
import { computed, ref } from 'vue'
import { formatPercent, formatTL } from '../../utils/format.js'

const props = defineProps({
  decision: { type: Object, default: null },
  rentalDays: { type: Number, default: 1 },
})

const emit = defineEmits(['edit-vehicle'])

const expanded = ref(false)

const hasCost = computed(() => props.decision?.has_cost_card === true)
const eksikBilesenler = computed(() => props.decision?.missing_fields ?? [])
const steps = computed(() => props.decision?.calculation_steps ?? [])

function formatStepValue(step) {
  if (step.value === null || step.value === undefined) return '—'
  const unit = step.unit || ''
  if (unit === 'oran') return formatPercent(Number(step.value) * 100)
  if (unit === '×') return `${Number(step.value).toFixed(2)}×`
  if (unit === 'gün') return `${step.value} gün`
  const money = formatTL(step.value)
  if (unit && unit !== 'TL') return `${money}/${unit.replace('TL/', '')}`
  return money
}
</script>

<template>
  <div v-if="!hasCost" class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
    {{ decision?.message || 'Maliyet hesaplanamıyor.' }}
    <ul v-if="eksikBilesenler.length" class="mt-2 list-disc space-y-0.5 pl-4 text-xs text-amber-800">
      <li v-for="item in eksikBilesenler" :key="item.field">{{ item.description }}</li>
    </ul>
    <button type="button" class="mt-2 font-semibold underline" @click="emit('edit-vehicle')">Maliyet gir</button>
  </div>

  <div v-else class="space-y-3">
    <div v-if="eksikBilesenler.length" class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
      <p class="font-semibold">
        {{ eksikBilesenler.length }} bileşenin verisi eksik — toplama dahil edilmedi.
      </p>
      <ul class="mt-1 list-disc space-y-0.5 pl-4">
        <li v-for="item in eksikBilesenler" :key="item.field">{{ item.description }}</li>
      </ul>
      <button type="button" class="mt-1 underline" @click="emit('edit-vehicle')">Düzelt</button>
    </div>

    <button
      type="button"
      class="flex w-full cursor-pointer items-center justify-between gap-2 text-left"
      @click="expanded = !expanded"
    >
      <h5 class="text-sm font-semibold text-slate-800">Hesaplama dökümü</h5>
      <span class="text-xs font-bold text-brand-600">
        {{ expanded ? 'Gizle ▴' : 'Detayları göster ▾' }}
      </span>
    </button>

    <div v-if="expanded" class="overflow-hidden rounded-lg border border-slate-200">
      <table class="w-full text-sm">
        <tbody>
          <tr
            v-for="step in steps"
            :key="step.order"
            class="border-b border-slate-100 last:border-0"
            :class="step.highlighted ? 'bg-red-50' : ''"
          >
            <td class="px-3 py-2 text-slate-600">
              {{ step.title }}
              <p class="text-[11px] font-normal text-slate-400">{{ step.description }}</p>
            </td>
            <td class="px-3 py-2 text-right align-top">
              <span :class="step.highlighted ? 'font-bold text-slate-900' : 'text-slate-800'">
                {{ formatStepValue(step) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
