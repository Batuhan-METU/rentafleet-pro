<script setup>
// Filo grafikleri (Day 11) — ECharts (vue-echarts).
//  * Yatay bar: en düşük sürüş skoruna sahip 5 araç (kritik filo).
//  * Çizgi: haftalık AI yakıt tasarruf trendi.
// Veri store.fleetAnalytics'ten gelir; tamamen Türkçe ve responsive.
import { computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useVehicleStore } from '../stores/vehicleStore.js'

use([CanvasRenderer, BarChart, LineChart, GridComponent, TooltipComponent])

const store = useVehicleStore()
onMounted(() => store.fetchFleetAnalytics())

const a = computed(() => store.fleetAnalytics)

function scoreColor(score) {
  if (score >= 80) return '#10b981'
  if (score >= 70) return '#f59e0b'
  return '#dc2626'
}

const hasLowest = computed(() => (a.value?.en_dusuk_skorlu_suruculer?.length ?? 0) > 0)
const hasTrend = computed(() => (a.value?.haftalik_yakit_tasarrufu?.length ?? 0) > 0)

// Grafik 1: en düşük skorlu 5 araç (yatay bar).
const lowestScoreOption = computed(() => {
  const rows = a.value?.en_dusuk_skorlu_suruculer ?? []
  return {
    grid: { left: 8, right: 24, top: 10, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: (v) => `${v} / 100`,
    },
    xAxis: {
      type: 'value',
      max: 100,
      splitLine: { lineStyle: { color: '#f1f5f9' } },
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: {
      type: 'category',
      inverse: true, // en düşük skor en üstte
      data: rows.map((r) => r.ad_soyad),
      axisLabel: { color: '#475569', fontWeight: 600 },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
    },
    series: [
      {
        type: 'bar',
        data: rows.map((r) => ({ value: r.skor, itemStyle: { color: scoreColor(r.skor) } })),
        barWidth: '55%',
        itemStyle: { borderRadius: [0, 6, 6, 0] },
        label: { show: true, position: 'right', color: '#334155', fontWeight: 700 },
      },
    ],
  }
})

// Grafik 2: haftalık yakıt tasarruf trendi (yumuşak çizgi).
const fuelTrendOption = computed(() => {
  const rows = a.value?.haftalik_yakit_tasarrufu ?? []
  return {
    grid: { left: 8, right: 20, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (v) => `%${v}`,
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((r) => r.gun),
      axisLabel: { color: '#94a3b8' },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#94a3b8', formatter: '%{value}' },
      splitLine: { lineStyle: { color: '#f1f5f9' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: rows.map((r) => r.tasarruf),
        symbolSize: 8,
        lineStyle: { width: 3, color: '#2563eb' },
        itemStyle: { color: '#2563eb' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(37,99,235,0.25)' },
              { offset: 1, color: 'rgba(37,99,235,0.02)' },
            ],
          },
        },
      },
    ],
  }
})
</script>

<template>
  <div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
    <!-- Kritik filo: en düşük skorlar -->
    <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div class="mb-3 flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full bg-red-500"></span>
        <h3 class="text-sm font-bold text-slate-800">En Düşük Sürüş Skoruna Sahip Sürücüler</h3>
      </div>
      <!-- Sabit yükseklikli kapsayıcı: ECharts'in sonsuz büyüme döngüsünü önler. -->
      <div class="h-72 w-full overflow-hidden">
        <VChart v-if="hasLowest" :option="lowestScoreOption" autoresize style="height: 100%; width: 100%" />
        <div v-else class="grid h-full place-items-center text-sm text-slate-400">Veri yükleniyor...</div>
      </div>
    </div>

    <!-- Yakıt tasarruf trendi -->
    <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div class="mb-3 flex items-center gap-2">
        <span class="h-2.5 w-2.5 rounded-full bg-brand-500"></span>
        <h3 class="text-sm font-bold text-slate-800">AI Yakıt Tasarruf Trendi (Haftalık)</h3>
      </div>
      <!-- Sabit yükseklikli kapsayıcı: ECharts'in sonsuz büyüme döngüsünü önler. -->
      <div class="h-72 w-full overflow-hidden">
        <VChart v-if="hasTrend" :option="fuelTrendOption" autoresize style="height: 100%; width: 100%" />
        <div v-else class="grid h-full place-items-center text-sm text-slate-400">Veri yükleniyor...</div>
      </div>
    </div>
  </div>
</template>
