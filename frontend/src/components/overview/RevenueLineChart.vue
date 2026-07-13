<script setup>
import { computed } from 'vue'
import { formatTL } from '../../utils/format.js'

const props = defineProps({
  data: { type: Array, default: () => [] },
  height: { type: Number, default: 160 },
})

const PAD_TOP = 12
const PAD_BOTTOM = 8

const maxValue = computed(() =>
  Math.max(...props.data.map((d) => d.gelir ?? 0), 1),
)

const points = computed(() => {
  const n = props.data.length
  const step = n > 1 ? 100 / (n - 1) : 0
  return props.data.map((d, i) => {
    const value = d.gelir ?? 0
    const ratio = maxValue.value ? value / maxValue.value : 0
    return {
      x: n > 1 ? i * step : 50,
      y: 100 - PAD_BOTTOM - ratio * (100 - PAD_TOP - PAD_BOTTOM),
      value,
      label: d.ay,
    }
  })
})

// Catmull-Rom -> kübik Bezier dönüşümü: noktalar arasında yumuşak/eğrisel
// bir çizgi üretir (düz kırık çizgi yerine).
const linePath = computed(() => {
  const pts = points.value
  if (!pts.length) return ''
  if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`

  let d = `M ${pts[0].x} ${pts[0].y}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[i + 2] || p2
    const cp1x = p1.x + (p2.x - p0.x) / 6
    const cp1y = p1.y + (p2.y - p0.y) / 6
    const cp2x = p2.x - (p3.x - p1.x) / 6
    const cp2y = p2.y - (p3.y - p1.y) / 6
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`
  }
  return d
})

const areaPath = computed(() => {
  const pts = points.value
  if (!pts.length) return ''
  const last = pts[pts.length - 1]
  const first = pts[0]
  return `${linePath.value} L ${last.x} 100 L ${first.x} 100 Z`
})
</script>

<template>
  <div class="rf-line-chart w-full">
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      class="w-full"
      :style="{ height: `${height}px` }"
      role="img"
      aria-label="Aylık gelir trendi çizgi grafiği"
    >
      <defs>
        <linearGradient id="rf-line-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--primary-color)" stop-opacity="0.32" />
          <stop offset="100%" stop-color="var(--primary-color)" stop-opacity="0" />
        </linearGradient>
        <linearGradient id="rf-line-stroke" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="var(--primary-color)" />
          <stop offset="100%" stop-color="var(--secondary-color)" />
        </linearGradient>
      </defs>

      <line x1="0" y1="99" x2="100" y2="99" stroke="#e2e8f0" stroke-width="0.3" />

      <path :d="areaPath" fill="url(#rf-line-area)" class="rf-line-area" />
      <path
        :d="linePath"
        fill="none"
        stroke="url(#rf-line-stroke)"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
        vector-effect="non-scaling-stroke"
        class="rf-line-stroke"
      />

      <circle
        v-for="(pt, idx) in points"
        :key="idx"
        :cx="pt.x"
        :cy="pt.y"
        r="1.3"
        fill="white"
        stroke="var(--primary-color)"
        stroke-width="0.9"
        vector-effect="non-scaling-stroke"
        class="rf-line-dot"
        :style="{ animationDelay: `${idx * 45}ms` }"
      >
        <title>{{ pt.label }}: {{ formatTL(pt.value) }}</title>
      </circle>
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
.rf-line-area {
  animation: rf-line-fade 0.8s ease both;
}

.rf-line-stroke {
  stroke-dasharray: 400;
  stroke-dashoffset: 400;
  animation: rf-line-draw 1s cubic-bezier(0.34, 1, 0.64, 1) both;
}

.rf-line-dot {
  opacity: 0;
  animation: rf-line-fade 0.5s ease both;
}

@keyframes rf-line-draw {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes rf-line-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
