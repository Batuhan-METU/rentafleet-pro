<script setup>
import { onBeforeUnmount, ref } from 'vue'
import VehicleDetailSidebar from '../components/vehicle-detail/VehicleDetailSidebar.vue'
import VehicleDetailComingSoon from '../components/vehicle-detail/VehicleDetailComingSoon.vue'
import VehicleDetailOverview from '../components/vehicle-detail/VehicleDetailOverview.vue'
import VehicleFinancingDetails from '../components/vehicle-detail/VehicleFinancingDetails.vue'
import VehicleInsurancePolicies from '../components/vehicle-detail/VehicleInsurancePolicies.vue'
import VehicleRentalHistory from '../components/vehicle-detail/VehicleRentalHistory.vue'
import VehicleDocuments from '../components/vehicle-detail/VehicleDocuments.vue'
import { VEHICLE_DETAIL_TABS } from '../utils/vehicleDetailTabs.js'

defineProps({
  vehicle: { type: Object, default: null },
})
const emit = defineEmits(['close', 'edit'])

const activeTab = ref('overview')
const displayedTab = ref('overview')
const transitioning = ref(false)
let transitionTimer = null

const TAB_SWITCH_DELAY_MS = 500

function switchTab(tabId) {
  if (!tabId || tabId === activeTab.value) return
  activeTab.value = tabId
  transitioning.value = true
  clearTimeout(transitionTimer)
  transitionTimer = setTimeout(() => {
    displayedTab.value = tabId
    transitioning.value = false
  }, TAB_SWITCH_DELAY_MS)
}

function activeTabMeta() {
  return VEHICLE_DETAIL_TABS.find((tab) => tab.id === displayedTab.value)
}

onBeforeUnmount(() => clearTimeout(transitionTimer))
</script>

<template>
  <div v-if="vehicle">
    <button
      type="button"
      class="mb-5 flex items-center gap-2 text-sm font-bold text-slate-600 hover:text-slate-900"
      @click="emit('close')"
    >
      <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
      <span class="underline underline-offset-2">Tüm Araçlara Dön</span>
    </button>

    <div class="flex gap-6">
      <VehicleDetailSidebar :active-tab="activeTab" @select="switchTab" />

      <div class="min-w-0 flex-1">
        <div v-if="transitioning" class="grid place-items-center py-24">
          <div class="h-9 w-9 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
        </div>
        <Transition v-else name="vd-fade" mode="out-in">
          <div :key="displayedTab">
            <VehicleDetailOverview
              v-if="displayedTab === 'overview'"
              :vehicle="vehicle"
              @edit="emit('edit', $event)"
              @switch-tab="switchTab"
            />
            <VehicleFinancingDetails v-else-if="displayedTab === 'financing'" :vehicle-id="vehicle.id" />
            <VehicleInsurancePolicies
              v-else-if="displayedTab === 'insurance-policies'"
              :vehicle-id="vehicle.id"
              :vehicle="vehicle"
              @edit="emit('edit', $event)"
            />
            <VehicleRentalHistory v-else-if="displayedTab === 'rentals'" :vehicle-id="vehicle.id" />
            <VehicleDocuments v-else-if="displayedTab === 'files'" :vehicle-id="vehicle.id" />
            <VehicleDetailComingSoon v-else :label="activeTabMeta()?.label ?? ''" />
          </div>
        </Transition>
      </div>
    </div>
  </div>

  <div v-else class="grid h-full place-items-center">
    <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
  </div>
</template>

<style scoped>
.vd-fade-enter-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.vd-fade-enter-from {
  opacity: 0;
  transform: translateY(4px);
}
</style>
