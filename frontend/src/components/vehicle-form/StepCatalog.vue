<script setup>
defineProps({
  form: { type: Object, required: true },
})
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-1 text-sm font-semibold text-slate-900">Katalog Bilgileri</h3>
    <p class="mb-4 text-xs text-slate-500">
      Şasi numarasını buradan girin — aracın diğer tüm bilgileri kaydettikten
      sonra "Ruhsat Bilgileri" adımında da aynı numarayla görünür.
    </p>
    <div class="grid grid-cols-2 gap-4 md:grid-cols-3">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Şasi Numarası</span>
        <input v-model="form.plate_chassis" class="vf-input" maxlength="32" />
      </label>
    </div>
  </section>
</template>
