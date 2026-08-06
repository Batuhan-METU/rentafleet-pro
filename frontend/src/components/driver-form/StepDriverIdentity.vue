<script setup>
import DatePicker from '../vehicle-form/DatePicker.vue'

defineProps({
  form: { type: Object, required: true },
})

const GENDERS = [
  { value: 'MALE', label: 'Erkek' },
  { value: 'FEMALE', label: 'Kadın' },
  { value: 'OTHER', label: 'Diğer' },
]
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-1 text-sm font-semibold text-slate-900">Kimlik &amp; İletişim</h3>
    <p class="mb-4 text-xs text-slate-500">Sürücünün kimlik ve iletişim bilgileri.</p>
    <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Ad <span class="text-rose-500">*</span></span>
        <input v-model="form.first_name" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Soyad <span class="text-rose-500">*</span></span>
        <input v-model="form.last_name" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">TC Kimlik No <span class="text-rose-500">*</span></span>
        <input v-model="form.national_id" class="vf-input" maxlength="11" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Doğum Tarihi <span class="text-rose-500">*</span></span>
        <DatePicker v-model="form.birth_date" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Cinsiyet</span>
        <select v-model="form.gender" class="vf-input">
          <option v-for="g in GENDERS" :key="g.value" :value="g.value">{{ g.label }}</option>
        </select>
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Telefon <span class="text-rose-500">*</span></span>
        <input v-model="form.phone" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">E-posta</span>
        <input v-model="form.email" type="email" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Şehir <span class="text-rose-500">*</span></span>
        <input v-model="form.city" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Meslek</span>
        <input v-model="form.occupation" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Aylık Gelir (TL)</span>
        <input v-model="form.monthly_income" type="number" step="0.01" class="vf-input" />
      </label>
    </div>
  </section>
</template>
