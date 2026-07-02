<script setup>
import { computed } from 'vue'

const props = defineProps({
  vehicle: { type: Object, required: true },
})

const emit = defineEmits(['select'])

const STATUS_FALLBACK = {
  label: 'Bilinmiyor',
  badge: 'bg-slate-100 text-slate-600 ring-slate-500/20',
  dot: 'bg-slate-400',
}

const status = computed(() => props.vehicle.statusInfo ?? STATUS_FALLBACK)

const kmFormatter = new Intl.NumberFormat('tr-TR')
const formattedKm = computed(() => `${kmFormatter.format(props.vehicle.current_km ?? 0)} km`)
</script>

<template>
  <article
    role="button"
    tabindex="0"
    class="group flex cursor-pointer flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
    @click="emit('select', vehicle)"
    @keydown.enter="emit('select', vehicle)"
    @keydown.space.prevent="emit('select', vehicle)"
  >
    <div class="flex items-start justify-between gap-3">
      <span
        class="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1 text-base font-extrabold tracking-wide text-slate-800"
      >
        {{ vehicle.plate_number }}
      </span>
      <span
        class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset"
        :class="status.badge"
      >
        <span class="h-1.5 w-1.5 rounded-full" :class="status.dot"></span>
        {{ status.label }}
      </span>
    </div>

    <h3 class="mt-4 text-lg font-semibold text-slate-900">
      {{ vehicle.brand }} {{ vehicle.model }}
    </h3>
    <p v-if="vehicle.sinif_etiketi" class="mt-1 text-sm font-medium text-brand-700">
      ({{ vehicle.sinif_etiketi }})
    </p>
    <p v-if="vehicle.sipp_code" class="mt-0.5 text-xs text-slate-400" title="SIPP kodu">
      SIPP: {{ vehicle.sipp_code }}
    </p>

    <dl class="mt-4 space-y-2.5 border-t border-dashed border-slate-200 pt-3 text-sm">
      <div class="flex items-center justify-between">
        <dt class="text-slate-500">Üretim Yılı</dt>
        <dd class="font-semibold text-slate-800">{{ vehicle.production_year }}</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500">Mevcut Kilometre</dt>
        <dd class="font-semibold text-slate-800">{{ formattedKm }}</dd>
      </div>
    </dl>

    <p class="mt-3 flex items-center justify-end gap-1 text-sm font-semibold text-brand-600 opacity-0 transition-opacity group-hover:opacity-100">
      Detayları gör
      <span aria-hidden="true">→</span>
    </p>
  </article>
</template>
