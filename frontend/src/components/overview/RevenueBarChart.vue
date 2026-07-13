<script setup>
import { computed } from 'vue'
import { formatTL } from '../../utils/format.js'

const props = defineProps({
  data: { type: Array, default: () => [] },
  height: { type: Number, default: 160 },
})

const maxValue = computed(() =>
  Math.max(...props.data.map((d) => d.gelir ?? 0), 1),
)

const bars = computed(() => {
  const w = 100 / props.data.length
  const gap = w * 0.22
  const barW = w - gap

  return props.data.map((d, i) => {
    const value = d.gelir ?? 0
    const h = maxValue.value ? (value / maxValue.value) * 100 : 0
    return {
      label: d.ay,
      value,
      x: i * w + gap / 2,
      width: barW,
      height: Math.max(h, value > 0 ? 4 : 0),
      y: 100 - Math.max(h, value > 0 ? 4 : 0),
    }
  })
})
</script>

<template>
  <div class="rf-bar-chart w-full">
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      class="w-full"
      :style="{ height: `${height}px` }"
      role="img"
      aria-label="Aylık gelir grafiği"
    >
      <defs>
        <linearGradient id="rf-bar-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#818cf8" />
          <stop offset="100%" stop-color="#22d3ee" />
        </linearGradient>
      </defs>

      <line x1="0" y1="99" x2="100" y2="99" stroke="#e2e8f0" stroke-width="0.3" />

      <rect
        v-for="(bar, idx) in bars"
        :key="idx"
        :x="bar.x"
        :y="bar.y"
        :width="bar.width"
        :height="bar.height"
        rx="1.5"
        fill="url(#rf-bar-grad)"
        class="rf-bar-segment origin-bottom"
        :style="{ animationDelay: `${idx * 60}ms` }"
      >
        <title>{{ bar.label }}: {{ formatTL(bar.value) }}</title>
      </rect>
    </svg>

    <div class="mt-2 grid grid-cols-12 gap-0.5 text-center">
      <span
        v-for="(d, i) in data"
        :key="i"
        class="text-[9px] font-semibold uppercase tracking-wide text-slate-400"
      >
        {{ d.ay }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.rf-bar-segment {
  animation: rf-bar-grow 0.7s cubic-bezier(0.34, 1.2, 0.64, 1) both;
}

@keyframes rf-bar-grow {
  from {
    transform: scaleY(0);
    opacity: 0.4;
  }
  to {
    transform: scaleY(1);
    opacity: 1;
  }
}
</style>
