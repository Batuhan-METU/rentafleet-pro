<script setup>
import DatePicker from './DatePicker.vue'

defineProps({
  form: { type: Object, required: true },
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-1 text-sm font-semibold text-slate-900">Muayene/TÜV Bilgileri</h3>
    <p class="mb-4 text-xs text-slate-500">Aracın periyodik muayene geçerlilik tarihi.</p>
    <div class="grid grid-cols-2 gap-4 md:grid-cols-3">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Muayene Geçerlilik Tarihi</span>
        <DatePicker v-model="form.registration.inspection_valid_until" />
      </label>
    </div>
  </section>
</template>
