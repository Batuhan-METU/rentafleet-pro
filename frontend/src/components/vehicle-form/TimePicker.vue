<script setup>
// DatePicker.vue'nun saat karşılığı — native <input type="time"> yerine,
// projedeki diğer seçiciler gibi tamamen tıklama/seçmeli bir bileşen.
// v-model "HH:MM" string ile çalışır (backend TimeField'ının kabul ettiği format).
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'))
const MINUTES = ['00', '15', '30', '45']

const hour = computed(() => props.modelValue?.split(':')[0] ?? '10')
const minute = computed(() => props.modelValue?.split(':')[1] ?? '00')

function setHour(event) {
  emit('update:modelValue', `${event.target.value}:${minute.value}`)
}
function setMinute(event) {
  emit('update:modelValue', `${hour.value}:${event.target.value}`)
}
</script>

<template>
  <div class="flex items-center gap-1.5">
    <select
      class="vf-input w-auto cursor-pointer text-center"
      :value="hour"
      @change="setHour"
    >
      <option v-for="h in HOURS" :key="h" :value="h">{{ h }}</option>
    </select>
    <span class="font-bold text-slate-400">:</span>
    <select
      class="vf-input w-auto cursor-pointer text-center"
      :value="minute"
      @change="setMinute"
    >
      <option v-for="m in MINUTES" :key="m" :value="m">{{ m }}</option>
    </select>
  </div>
</template>
