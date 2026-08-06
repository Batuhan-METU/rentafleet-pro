<script setup>
import InsurancePolicyList from '../finance/InsurancePolicyList.vue'

defineProps({
  vehicleId: { type: Number, required: true },
  vehicle: { type: Object, required: true },
})
const emit = defineEmits(['edit'])
</script>

<template>
  <InsurancePolicyList :vehicle-id="vehicleId" @edit="emit('edit', vehicle)" />
</template>
