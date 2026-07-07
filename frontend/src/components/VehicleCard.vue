<script setup>
import { computed } from 'vue'

const props = defineProps({
  vehicle: { type: Object, required: true },
})

const emit = defineEmits(['select'])

const STATUS_FALLBACK = {
  label: 'Bilinmiyor',
  badge: 'bg-white/50 text-slate-600 ring-slate-400/30',
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
    class="group rf-glass rf-interactive flex cursor-pointer flex-col rounded-3xl p-5 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:ring-offset-2"
    @click="emit('select', vehicle)"
    @keydown.enter="emit('select', vehicle)"
    @keydown.space.prevent="emit('select', vehicle)"
  >
    <div class="flex items-start justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <span class="rounded-xl border border-white/50 bg-white/40 px-3 py-1.5 text-sm font-black tracking-wide text-slate-900 backdrop-blur-sm">
          {{ vehicle.plate_number }}
        </span>
        <span v-if="vehicle.sipp_code" class="rf-sipp-pill">{{ vehicle.sipp_code }}</span>
      </div>
      <span
        class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold ring-1 ring-inset backdrop-blur-sm"
        :class="status.badge"
      >
        <span class="h-1.5 w-1.5 rounded-full" :class="status.dot" />
        {{ status.label }}
      </span>
    </div>

    <h3 class="mt-4 text-xl font-black tracking-tight text-slate-900">
      {{ vehicle.brand }} {{ vehicle.model }}
    </h3>
    <p v-if="vehicle.sinif_etiketi" class="mt-1 text-sm font-medium text-slate-500/80">
      {{ vehicle.sinif_etiketi }}
    </p>

    <dl class="mt-5 space-y-2.5 border-t border-white/30 pt-4 text-sm">
      <div class="flex items-center justify-between">
        <dt class="text-slate-500/80">Üretim Yılı</dt>
        <dd class="font-bold text-slate-800">{{ vehicle.production_year }}</dd>
      </div>
      <div class="flex items-center justify-between">
        <dt class="text-slate-500/80">Kilometre</dt>
        <dd class="font-bold text-slate-800">{{ formattedKm }}</dd>
      </div>
    </dl>

    <p class="mt-4 flex items-center justify-end gap-1 text-sm font-bold text-brand-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
      Detayları gör
      <span aria-hidden="true">→</span>
    </p>
  </article>
</template>
