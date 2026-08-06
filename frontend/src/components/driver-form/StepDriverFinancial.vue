<script setup>
defineProps({
  form: { type: Object, required: true },
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-1 text-sm font-semibold text-slate-900">Finans &amp; Risk</h3>
    <p class="mb-4 text-xs text-slate-500">
      Bu bilgiler risk skorunu doğrudan etkiler — kayıt sonrası skor otomatik hesaplanır.
    </p>
    <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Findeks Skoru</span>
        <input v-model="form.findeks_score" type="number" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Ödeme Gecikme Sayısı</span>
        <input v-model="form.payment_delay_count" type="number" class="vf-input" />
      </label>
    </div>
  </section>
</template>
