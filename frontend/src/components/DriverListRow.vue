<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'
import maleIcon from './icons/3233508.png'
import femaleIcon from './icons/3577099.png'

const props = defineProps({
  driver: { type: Object, required: true },
})

const emit = defineEmits(['select', 'auto-rent'])

const workflow = useRentalWorkflowStore()
const { readyForDriverPick } = storeToRefs(workflow)

const riskScore = computed(() => props.driver.risk_score ?? null)

const riskBadgeClass = computed(() => {
  const value = riskScore.value
  if (value === null) return 'bg-slate-100 text-slate-400'
  if (value <= 30) return 'bg-emerald-100 text-emerald-700 ring-emerald-300/50'
  if (value <= 60) return 'bg-amber-100 text-amber-700 ring-amber-300/50'
  return 'bg-red-100 text-red-700 ring-red-300/50'
})

const avatarClass = computed(() => {
  const value = riskScore.value
  if (value === null) return 'bg-slate-200 text-slate-500'
  if (value <= 30) return 'bg-emerald-500/15 text-emerald-700'
  if (value <= 60) return 'bg-amber-500/15 text-amber-700'
  return 'bg-red-500/15 text-red-700'
})

const rental = computed(() => props.driver.active_rental)
const canQuickRent = computed(() =>
  readyForDriverPick.value
  && !rental.value
  && !props.driver.is_blacklisted
  && props.driver.risk_approved !== false
  && (props.driver.vehicle_eligible !== false),
)

const avatarIcon = computed(() => (props.driver.gender === 'FEMALE' ? femaleIcon : maleIcon))
</script>

<template>
  <tr
    role="button"
    tabindex="0"
    class="group cursor-pointer border-b border-slate-100 transition-colors duration-150 last:border-0 hover:bg-slate-50/80 focus:outline-none focus:bg-slate-50"
    @click="emit('select', driver)"
    @keydown.enter="emit('select', driver)"
    @keydown.space.prevent="emit('select', driver)"
  >
    <td class="py-3 pl-4 pr-3">
      <div class="flex min-w-0 items-center gap-3">
        <div class="grid h-10 w-10 shrink-0 place-items-center overflow-hidden rounded-xl" :class="avatarClass">
          <img :src="avatarIcon" :alt="driver.gender_display" class="h-7 w-7 object-contain" />
        </div>
        <div class="min-w-0">
          <p class="truncate font-bold text-slate-900">{{ driver.full_name }}</p>
          <p class="text-xs text-slate-500">{{ driver.age }} yaş · {{ driver.gender_display }}</p>
        </div>
      </div>
    </td>

    <td class="py-3 pr-3 text-slate-700">{{ driver.city }}</td>

    <td class="py-3 pr-3 text-slate-700">{{ driver.license_class }} · {{ driver.license_number }}</td>

    <td class="py-3 pr-3 text-center font-bold text-slate-800">{{ driver.total_rentals }}</td>

    <td class="py-3 pr-3">
      <span
        class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-black ring-1"
        :class="riskBadgeClass"
      >
        {{ riskScore !== null ? riskScore : '··' }}
      </span>
      <span v-if="driver.is_blacklisted" class="ml-1.5 inline-flex items-center rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-bold text-red-600 ring-1 ring-red-300/40">
        Kara Liste
      </span>
    </td>

    <td class="py-3 pr-3">
      <template v-if="rental">
        <p class="font-bold text-slate-900">{{ rental.plate_number }}</p>
        <p class="text-xs text-slate-500">{{ rental.brand_model }}</p>
      </template>
      <span v-else class="text-xs text-slate-400">Aktif kiralama yok</span>
    </td>

    <td class="py-3 pr-4 text-right">
      <button
        v-if="canQuickRent"
        type="button"
        class="rf-btn-primary !px-3 !py-1.5 text-xs"
        @click.stop="emit('auto-rent', driver)"
      >
        Otomatik Kiralama
      </button>
      <span v-else class="inline-flex items-center gap-1 text-sm font-bold text-brand-600 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
        Profili gör →
      </span>
    </td>
  </tr>
</template>
