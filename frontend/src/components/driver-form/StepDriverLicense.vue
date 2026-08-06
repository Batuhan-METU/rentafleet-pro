<script setup>
import DatePicker from '../vehicle-form/DatePicker.vue'

defineProps({
  form: { type: Object, required: true },
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-1 text-sm font-semibold text-slate-900">Ehliyet</h3>
    <p class="mb-4 text-xs text-slate-500">Ehliyet bilgileri — risk hesaplamasının bir kısmı buradan beslenir.</p>
    <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Ehliyet No <span class="text-rose-500">*</span></span>
        <input v-model="form.license_number" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Sınıf</span>
        <input v-model="form.license_class" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Ehliyet Alım Tarihi <span class="text-rose-500">*</span></span>
        <DatePicker v-model="form.license_issue_date" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Ceza Puanı</span>
        <input v-model="form.license_points" type="number" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Ceza Sayısı</span>
        <input v-model="form.license_penalty_count" type="number" class="vf-input" />
      </label>
    </div>
  </section>
</template>
