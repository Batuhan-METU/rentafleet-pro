<script setup>
import DatePicker from './DatePicker.vue'

defineProps({
  form: { type: Object, required: true },
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-1 text-sm font-semibold text-slate-900">Fatura Bilgileri</h3>
    <p class="mb-4 text-xs text-slate-500">Satın alma faturasının kendisine ait bilgiler.</p>
    <div class="grid grid-cols-2 gap-4 md:grid-cols-3">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Fatura Tarihi</span>
        <DatePicker v-model="form.purchase_invoice_date" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Fatura Numarası</span>
        <input v-model="form.registration.invoice_number" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Fatura Tutarı (TL)</span>
        <input v-model="form.registration.invoice_amount" type="number" step="0.01" class="vf-input" />
      </label>
    </div>
  </section>
</template>
