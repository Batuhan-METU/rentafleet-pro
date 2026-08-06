<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'

const emit = defineEmits(['cancel'])

const workflow = useRentalWorkflowStore()
const { showWorkflowBanner, progressStep } = storeToRefs(workflow)

const steps = [
  { id: 'pricing', label: '1. Fiyatlandırma' },
  { id: 'driver', label: '2. Sürücü Seç' },
  { id: 'rental', label: '3. Kiralama' },
]

const currentIdx = computed(() =>
  steps.findIndex((s) => s.id === progressStep.value),
)

function cancelWorkflow() {
  workflow.clear()
  emit('cancel')
}
</script>

<template>
  <div v-if="showWorkflowBanner" class="rf-glass-strong rounded-3xl border border-brand-200/60 p-5">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <p class="text-xs font-bold uppercase tracking-widest text-brand-600">Kiralama Süreci</p>
      <button
        type="button"
        class="rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-bold text-rose-700 transition hover:bg-rose-100"
        @click="cancelWorkflow"
      >
        Kiralamayı İptal
      </button>
    </div>

    <div class="mt-4 flex flex-wrap gap-2">
      <span
        v-for="(step, idx) in steps"
        :key="step.id"
        class="rounded-full px-3 py-1 text-xs font-bold transition"
        :class="idx < currentIdx
          ? 'bg-emerald-100 text-emerald-700'
          : idx === currentIdx
            ? 'bg-brand-600 text-white'
            : 'bg-slate-100 text-slate-400'"
      >
        {{ step.label }}
      </span>
    </div>

    <p class="mt-3 text-sm font-semibold text-slate-800">{{ workflow.stepLabel }}</p>
    <slot />
  </div>
</template>
