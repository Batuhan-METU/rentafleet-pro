<script setup>
import { computed, ref } from 'vue'
import { formatTL } from '../../utils/format.js'

const props = defineProps({
  performance: { type: Object, default: null },
  birikenKar: { type: Number, default: null },
})

const open = ref(true)

const hasData = computed(() => (props.performance?.rental_count ?? 0) > 0)
// Maliyet motoru bileşen verisi eksikse backend bu alanları null döner —
// eskiden ?? 0 ile sessizce sıfıra düşürülüyordu, artık "veri eksik" (—)
// olarak kalması bilinçli (§1.5: Bilinmiyor ≠ Sıfır).
const ortalamaKarGun = computed(() => props.performance?.avg_profit_per_day ?? null)
const costDataMissing = computed(() => hasData.value && props.performance?.total_cost == null)

const karMarji = computed(() => {
  const gelir = props.performance?.total_revenue ?? 0
  const kar = props.performance?.accumulated_profit ?? props.birikenKar
  if (kar == null || gelir <= 0) return null
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
        <p
          class="text-xl font-bold"
          :class="birikenKar == null ? 'text-slate-400' : birikenKar >= 0 ? 'text-slate-900' : 'text-red-600'"
        >
          {{ formatTL(birikenKar) }}
        </p>
        <p v-if="performance?.rental_count" class="text-xs text-slate-500">
          {{ performance.rental_count }} kiralama · {{ performance.rented_days }} gün
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
            <dd class="font-semibold">{{ formatTL(performance.total_revenue) }}</dd>
          </div>
          <div class="rounded-md bg-white px-2 py-2">
            <dt class="text-slate-400">Maliyet</dt>
            <dd class="font-semibold">{{ formatTL(performance.total_cost) }}</dd>
          </div>
          <div class="rounded-md bg-white px-2 py-2">
            <dt class="text-slate-400">Ort. kâr/gün</dt>
            <dd
              class="font-semibold"
              :class="ortalamaKarGun == null ? 'text-slate-400' : ortalamaKarGun >= 0 ? 'text-emerald-700' : 'text-red-600'"
            >
              {{ formatTL(ortalamaKarGun) }}
            </dd>
          </div>
        </dl>
        <p v-if="karMarji != null" class="mt-2 text-xs text-slate-500">
          Net marj: <strong>%{{ karMarji }}</strong>
        </p>
        <p v-else-if="costDataMissing" class="mt-2 text-xs text-amber-700">
          Maliyet verisi eksik (finansman/sigorta/genel gider bilgisi tamamlanmamış) — kâr marjı hesaplanamıyor.
        </p>
      </template>
    </div>
  </div>
</template>
