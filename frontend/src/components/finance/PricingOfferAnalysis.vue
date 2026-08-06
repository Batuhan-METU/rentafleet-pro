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
  const d = props.analysis?.status
  if (d === 'loss') return 'bg-red-50 text-red-800 border-red-200'
  if (d === 'break_even') return 'bg-amber-50 text-amber-900 border-amber-200'
  return 'bg-emerald-50 text-emerald-800 border-emerald-200'
})
</script>

<template>
  <div v-if="hasAnalysis" class="rounded-lg border px-3 py-2.5 text-sm" :class="statusClass">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <span class="font-medium">{{ analysis.status_label }}</span>
      <span class="font-bold">
        {{ analysis.estimated_profit >= 0 ? '+' : '' }}{{ formatTL(analysis.estimated_profit) }}
        <span class="text-xs font-normal opacity-80">
          ({{ formatTL(analysis.offered_daily) }}/gün)
        </span>
      </span>
    </div>
    <p v-if="!compact" class="mt-1 text-xs opacity-80">{{ analysis.status_message }}</p>
    <p v-if="loading" class="mt-1 text-xs opacity-60">Güncelleniyor…</p>
  </div>
</template>
