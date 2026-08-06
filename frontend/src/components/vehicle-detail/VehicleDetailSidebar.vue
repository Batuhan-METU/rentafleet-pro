<script setup>
import { ref } from 'vue'
import { VEHICLE_DETAIL_TABS } from '../../utils/vehicleDetailTabs.js'

defineProps({
  activeTab: { type: String, required: true },
})
const emit = defineEmits(['select'])

// Sayfada büyük yer kaplamaması için sekme listesi varsayılan olarak
// daraltılmış (yalnızca genişletme oku görünür); kullanıcı tıklayınca
// tamamı açılır, tekrar tıklayınca daralır.
const expanded = ref(false)
</script>

<template>
  <nav
    class="shrink-0 border-r border-slate-200 pr-2 transition-[width] duration-200"
    :class="expanded ? 'w-72' : 'w-10'"
  >
    <button
      type="button"
      class="mb-2 grid h-8 w-8 place-items-center rounded-lg text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600"
      :title="expanded ? 'Daralt' : 'Genişlet'"
      @click="expanded = !expanded"
    >
      <svg
        class="h-4 w-4 transition-transform duration-200"
        :class="{ 'rotate-180': expanded }"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        stroke-width="2"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
      </svg>
    </button>

    <div v-if="expanded" class="space-y-1">
      <button
        v-for="tab in VEHICLE_DETAIL_TABS"
        :key="tab.id"
        type="button"
        class="flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-left text-sm font-semibold transition-colors"
        :class="activeTab === tab.id
          ? 'bg-brand-50 text-brand-700'
          : 'text-slate-600 hover:bg-slate-50'"
        @click="emit('select', tab.id)"
      >
        <span>{{ tab.label }}</span>
        <span
          v-if="!tab.ready"
          class="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold text-slate-400"
        >
          Yakında
        </span>
      </button>
    </div>
  </nav>
</template>
