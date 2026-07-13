<script setup>
import { computed } from 'vue'
import { formatTL } from '../../utils/format.js'

const props = defineProps({
  analysis: { type: Object, default: null },
  loading: { type: Boolean, default: false },
  rentalDays: { type: Number, default: 1 },
  compact: { type: Boolean, default: false },
})

const hasAnalysis = computed(() => props.analysis != null)

const statusClass = computed(() => {
  const d = props.analysis?.durum
  if (d === 'zarar') return 'bg-red-50 text-red-800 border-red-200'
  if (d === 'taban') return 'bg-amber-50 text-amber-900 border-amber-200'
  return 'bg-emerald-50 text-emerald-800 border-emerald-200'
})
</script>

<template>
  <div v-if="hasAnalysis" class="rounded-lg border px-3 py-2.5 text-sm" :class="statusClass">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <span class="font-medium">{{ analysis.durum_etiketi }}</span>
      <span class="font-bold">
        {{ analysis.tahmini_kar >= 0 ? '+' : '' }}{{ formatTL(analysis.tahmini_kar) }}
        <span class="text-xs font-normal opacity-80">
          ({{ formatTL(analysis.teklif_gunluk) }}/gün)
        </span>
      </span>
    </div>
    <p v-if="!compact" class="mt-1 text-xs opacity-80">{{ analysis.durum_mesaji }}</p>
    <p v-if="loading" class="mt-1 text-xs opacity-60">Güncelleniyor…</p>
  </div>
</template>
