<script setup>
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
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
      axisLabel: { color: '#94a3b8' },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: rows.map((r) => r.ad_soyad),
      axisLabel: { color: '#475569', fontWeight: 600 },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: 'rgba(226,232,240,0.6)' } },
    },
    series: [
      {
        type: 'bar',
        data: rows.map((r) => ({ value: r.skor, itemStyle: { color: scoreColor(r.skor) } })),
        barWidth: '55%',
        itemStyle: { borderRadius: [0, 8, 8, 0] },
        label: { show: true, position: 'right', color: '#334155', fontWeight: 700 },
      },
    ],
  }
})

const fuelTrendOption = computed(() => {
  const rows = a.value?.haftalik_yakit_tasarrufu ?? []
  const primary = getComputedStyle(document.documentElement).getPropertyValue('--primary-color').trim() || '#3b82f6'
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
      axisLine: { lineStyle: { color: 'rgba(226,232,240,0.6)' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#94a3b8', formatter: '%{value}' },
      splitLine: { lineStyle: { color: 'rgba(241,245,249,0.8)' } },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data: rows.map((r) => r.tasarruf),
        symbolSize: 8,
        lineStyle: { width: 3, color: primary },
        itemStyle: { color: primary },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: `${primary}40` },
              { offset: 1, color: `${primary}05` },
            ],
          },
        },
      },
    ],
  }
})
</script>

<template>
  <div class="mt-6 grid grid-cols-12 gap-4">
    <!-- Geniş: yakıt trendi -->
    <div class="rf-glass rf-interactive col-span-12 rounded-3xl p-6 lg:col-span-8">
      <div class="mb-4 flex items-center gap-3">
        <span class="rf-icon-ring !h-9 !w-9 shrink-0">
          <svg class="h-4 w-4 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </span>
        <div>
          <h3 class="text-base font-black text-slate-900">AI Yakıt Tasarruf Trendi</h3>
          <p class="text-xs text-slate-500/80">Haftalık performans eğrisi</p>
        </div>
      </div>
      <div class="h-72 w-full overflow-hidden">
        <VChart v-if="hasTrend" :option="fuelTrendOption" autoresize style="height: 100%; width: 100%" />
        <div v-else class="grid h-full place-items-center text-sm text-slate-400">Veri yükleniyor...</div>
      </div>
    </div>

    <!-- Dar: düşük skorlar -->
    <div class="rf-glass rf-interactive col-span-12 rounded-3xl p-6 lg:col-span-4">
      <div class="mb-4 flex items-center gap-3">
        <span class="rf-icon-ring !h-9 !w-9 shrink-0 !text-red-600">
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4a2 2 0 00-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3z" />
          </svg>
        </span>
        <div>
          <h3 class="text-base font-black text-slate-900">Risk Altındaki Sürücüler</h3>
          <p class="text-xs text-slate-500/80">En düşük 5 skor</p>
        </div>
      </div>
      <div class="h-72 w-full overflow-hidden">
        <VChart v-if="hasLowest" :option="lowestScoreOption" autoresize style="height: 100%; width: 100%" />
        <div v-else class="grid h-full place-items-center text-sm text-slate-400">Veri yükleniyor...</div>
      </div>
    </div>
  </div>
</template>
