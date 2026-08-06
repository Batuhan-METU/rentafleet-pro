<script setup>
import vehicleIcon from '../../../assets/vehicle-icon.png'

defineProps({
  activeTab: { type: String, required: true },
})
const emit = defineEmits(['select'])

const TABS = [
  { id: 'installments', label: 'Taksit Listesi' },
  { id: 'vehicles', label: 'Kredi Araç Listesi' },
]
</script>

<template>
  <nav class="w-56 shrink-0 space-y-1 border-r border-slate-200 pr-3">
    <button
      type="button"
      class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition-colors"
      :class="activeTab === 'installments' ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50'"
      @click="emit('select', 'installments')"
    >
      <svg class="h-4.5 w-4.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
        <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 8.25h19.5M2.25 8.25v10.5A2.25 2.25 0 004.5 21h15a2.25 2.25 0 002.25-2.25V8.25M2.25 8.25V5.25A2.25 2.25 0 014.5 3h15a2.25 2.25 0 012.25 2.25v3M6 15h4.5" />
      </svg>
      {{ TABS[0].label }}
    </button>
    <button
      type="button"
      class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition-colors"
      :class="activeTab === 'vehicles' ? 'bg-brand-50 text-brand-700' : 'text-slate-600 hover:bg-slate-50'"
      @click="emit('select', 'vehicles')"
    >
      <img :src="vehicleIcon" alt="" class="h-4.5 w-4.5 shrink-0 object-contain" />
      {{ TABS[1].label }}
    </button>
  </nav>
</template>
