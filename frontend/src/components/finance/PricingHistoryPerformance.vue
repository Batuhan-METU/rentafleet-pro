<script setup>
import { computed, ref } from 'vue'
import { formatTL } from '../../utils/format.js'

const props = defineProps({
  performance: { type: Object, default: null },
  birikenKar: { type: Number, default: 0 },
})

const open = ref(true)

const hasData = computed(() => (props.performance?.kiralama_sayisi ?? 0) > 0)
const ortalamaKarGun = computed(() => props.performance?.ortalama_kar_gun ?? 0)

const karMarji = computed(() => {
  const gelir = props.performance?.toplam_gelir ?? 0
  const kar = props.performance?.biriken_kar ?? props.birikenKar ?? 0
  if (gelir <= 0) return null
  return Math.round((kar / gelir) * 1000) / 10
})
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-slate-50">
    <button
      type="button"
      class="flex w-full items-center justify-between px-4 py-3 text-left"
      @click="open = !open"
    >
      <div>
        <p class="text-xs text-slate-500">Biriken net kâr</p>
        <p class="text-xl font-bold" :class="birikenKar >= 0 ? 'text-slate-900' : 'text-red-600'">
          {{ formatTL(birikenKar) }}
        </p>
        <p v-if="performance?.kiralama_sayisi" class="text-xs text-slate-500">
          {{ performance.kiralama_sayisi }} kiralama · {{ performance.kiralanan_gun }} gün
        </p>
      </div>
      <span class="text-xs text-slate-400">{{ open ? '▲' : '▼' }}</span>
    </button>

    <div v-if="open" class="border-t border-slate-200 px-4 pb-4 pt-3 text-sm">
      <p v-if="!hasData" class="text-slate-500">Henüz tamamlanan kiralama yok.</p>
      <template v-else>
        <dl class="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
          <div class="rounded-md bg-white px-2 py-2">
            <dt class="text-slate-400">Gelir</dt>
            <dd class="font-semibold">{{ formatTL(performance.toplam_gelir) }}</dd>
          </div>
          <div class="rounded-md bg-white px-2 py-2">
            <dt class="text-slate-400">Maliyet</dt>
            <dd class="font-semibold">{{ formatTL(performance.toplam_maliyet) }}</dd>
          </div>
          <div class="rounded-md bg-white px-2 py-2">
            <dt class="text-slate-400">Ort. kâr/gün</dt>
            <dd class="font-semibold" :class="ortalamaKarGun >= 0 ? 'text-emerald-700' : 'text-red-600'">
              {{ formatTL(ortalamaKarGun) }}
            </dd>
          </div>
        </dl>
        <p v-if="karMarji != null" class="mt-2 text-xs text-slate-500">
          Net marj: <strong>%{{ karMarji }}</strong>
        </p>
      </template>
    </div>
  </div>
</template>
