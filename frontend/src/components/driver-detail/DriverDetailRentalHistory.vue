<script setup>
defineProps({
  rentals: { type: Array, default: () => [] },
})
</script>

<template>
  <div>
    <div v-if="!rentals.length" class="rf-glass grid place-items-center rounded-3xl p-12 text-center text-slate-500">
      Bu sürücüye ait kiralama kaydı bulunamadı.
    </div>
    <ul v-else class="space-y-2">
      <li v-for="r in rentals" :key="r.id" class="rounded-lg border border-slate-100 bg-slate-50 px-4 py-3 text-sm">
        <span class="font-semibold text-slate-900">{{ r.plate_number }}</span>
        <span class="text-slate-600"> · {{ r.brand_model }}</span>
        <span class="ml-2 text-xs font-semibold text-brand-600">{{ r.status_label }}</span>
      </li>
    </ul>
  </div>
</template>
