<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { formatTL } from '../../utils/format.js'

const props = defineProps({
  data: { type: Array, default: () => [] },
  height: { type: Number, default: 160 },
})

const PAD_TOP = 16
const PAD_BOTTOM = 10

// Grafiği gerçek piksel genişliğinde ölçüp viewBox'ı buna eşitliyoruz —
// eskiden 0-100'lük bir viewBox'ı preserveAspectRatio="none" ile geniş bir
// kutuya oranti bozarak geriyordu; bu da eğrinin/noktaların X ve Y'de farklı
// ölçeklenmesine (oval noktalar, kopuk görünen segmentler) yol açıyordu.
// Piksel-birebir viewBox kullanınca ölçek her eksende 1:1 olur, bozulma kalmaz.
const containerEl = ref(null)
const containerWidth = ref(0)
let resizeObserver = null

onMounted(() => {
  if (containerEl.value) {
    containerWidth.value = containerEl.value.clientWidth
    resizeObserver = new ResizeObserver((entries) => {
      containerWidth.value = entries[0].contentRect.width
    })
    resizeObserver.observe(containerEl.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})

const width = computed(() => containerWidth.value || 600)

const maxValue = computed(() =>
  Math.max(...props.data.map((d) => d.gelir ?? 0), 1),
)

const points = computed(() => {
  const n = props.data.length
  const step = n > 1 ? width.value / (n - 1) : 0
  return props.data.map((d, i) => {
    const value = d.gelir ?? 0
    const ratio = maxValue.value ? value / maxValue.value : 0
    return {
      x: n > 1 ? i * step : width.value / 2,
      y: props.height - PAD_BOTTOM - ratio * (props.height - PAD_TOP - PAD_BOTTOM),
      value,
      label: d.ay,
    }
  })
})

// Catmull-Rom -> kübik Bezier dönüşümü: noktalar arasında yumuşak/eğrisel
// bir çizgi üretir (düz kırık çizgi yerine), tek parça sürekli bir path olarak.
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
  return `${linePath.value} L ${last.x} ${props.height} L ${first.x} ${props.height} Z`
})

const baselineY = computed(() => props.height - PAD_BOTTOM + 1)
</script>

<template>
  <div ref="containerEl" class="rf-line-chart w-full">
    <svg
      :viewBox="`0 0 ${width} ${height}`"
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

      <line x1="0" :y1="baselineY" :x2="width" :y2="baselineY" stroke="#e2e8f0" stroke-width="1" />

      <path :d="areaPath" fill="url(#rf-line-area)" class="rf-line-area" />
      <path
        :d="linePath"
        fill="none"
        stroke="url(#rf-line-stroke)"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="rf-line-stroke"
      />

      <circle
        v-for="(pt, idx) in points"
        :key="idx"
        :cx="pt.x"
        :cy="pt.y"
        r="3.5"
        fill="white"
        stroke="var(--primary-color)"
        stroke-width="2"
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
.rf-line-area,
.rf-line-stroke {
  opacity: 0;
  animation: rf-line-fade 0.6s ease both;
}

.rf-line-dot {
  opacity: 0;
  animation: rf-line-fade 0.5s ease both;
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
