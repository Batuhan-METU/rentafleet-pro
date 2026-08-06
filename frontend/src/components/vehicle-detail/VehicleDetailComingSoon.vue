<script setup>
defineProps({
  label: { type: String, required: true },
})
</script>

<template>
  <div class="grid place-items-center rounded-3xl border border-dashed border-slate-200 bg-slate-50/60 p-16 text-center">
    <div class="grid h-14 w-14 place-items-center rounded-full bg-slate-100 text-2xl text-slate-400">⏳</div>
    <p class="mt-4 text-base font-semibold text-slate-700">{{ label }} yakında</p>
    <p class="mt-1 text-sm text-slate-500">Bu bölüm henüz hazır değil, ilerleyen bir güncellemede eklenecek.</p>
  </div>
</template>
