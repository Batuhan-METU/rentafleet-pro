<script setup>
import { computed } from 'vue'

const props = defineProps({
  driver: { type: Object, required: true },
})

const emit = defineEmits(['select'])

const score = computed(() => props.driver.surus_skoru ?? null)

const scoreBadgeClass = computed(() => {
  const value = score.value
  if (value === null) return 'bg-slate-100 text-slate-400'
  if (value > 80) return 'bg-emerald-100 text-emerald-700'
  if (value >= 70) return 'bg-amber-100 text-amber-700'
  return 'bg-red-100 text-red-700'
})

const rental = computed(() => props.driver.aktif_kiralama)
const kmFmt = new Intl.NumberFormat('tr-TR')
</script>

<template>
  <article
    role="button"
    tabindex="0"
    class="group flex cursor-pointer flex-col rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2"
    @click="emit('select', driver)"
    @keydown.enter="emit('select', driver)"
    @keydown.space.prevent="emit('select', driver)"
  >
    <div class="flex items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-bold text-slate-900">{{ driver.ad_soyad }}</h3>
        <p class="text-sm text-slate-500">{{ driver.yas }} yaş · {{ driver.cinsiyet }}</p>
      </div>
      <span
        class="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold"
        :class="scoreBadgeClass"
        title="Sürüş Skoru"
      >
        <span aria-hidden="true">★</span>
        {{ score !== null ? score : '··' }}
      </span>
    </div>

    <dl class="mt-4 space-y-2 border-t border-dashed border-slate-200 pt-3 text-sm">
      <div class="flex justify-between">
        <dt class="text-slate-500">Ehliyet</dt>
        <dd class="font-semibold text-slate-800">{{ driver.license_class }} · {{ driver.license_number }}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-slate-500">Şehir</dt>
        <dd class="font-semibold text-slate-800">{{ driver.city }}</dd>
      </div>
      <div class="flex justify-between">
        <dt class="text-slate-500">Toplam Kiralama</dt>
        <dd class="font-semibold text-slate-800">{{ driver.toplam_kiralama }}</dd>
      </div>
    </dl>

    <div
      v-if="rental"
      class="mt-4 rounded-xl border border-blue-100 bg-blue-50 px-3 py-2.5 text-sm"
    >
      <p class="text-xs font-semibold uppercase tracking-wide text-blue-600">Aktif Kiralama</p>
          <p class="font-bold text-slate-800">{{ rental.plaka }}</p>
          <p class="mt-1 text-sm text-slate-600">{{ rental.marka_model_sinif || rental.marka_model }}</p>
      <p class="text-xs text-slate-600">{{ kmFmt.format(rental.guncel_km) }} km</p>
    </div>
    <div v-else class="mt-4 rounded-xl border border-dashed border-slate-200 px-3 py-2 text-center text-xs text-slate-400">
      Şu an aktif kiralama yok
    </div>

    <span
      v-if="driver.is_blacklisted"
      class="mt-3 inline-flex w-fit items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-semibold text-red-700"
    >
      Kara Liste
    </span>

    <p class="mt-3 flex items-center justify-end gap-1 text-sm font-semibold text-brand-600 opacity-0 transition-opacity group-hover:opacity-100">
      Profili gör →
    </p>
  </article>
</template>
