<script setup>
import { computed } from 'vue'

const props = defineProps({
  segments: {
    type: Array,
    default: () => [],
  },
  size: { type: Number, default: 240 },
})

const total = computed(() =>
  props.segments.reduce((sum, seg) => sum + Math.max(Number(seg.value) || 0, 0), 0),
)

const donutStyle = computed(() => {
  const segs = props.segments.filter((s) => (Number(s.value) || 0) > 0)
  if (!segs.length || total.value === 0) {
    return { background: 'conic-gradient(#e2e8f0 0deg 360deg)' }
  }

  let angle = 0
  const stops = segs.map((seg) => {
    const sweep = ((Number(seg.value) || 0) / total.value) * 360
    const start = angle
    angle += sweep
    return `${seg.color} ${start}deg ${angle}deg`
  })
  return { background: `conic-gradient(from -90deg, ${stops.join(', ')})` }
})

const legend = computed(() =>
  props.segments.map((seg) => ({
    ...seg,
    value: Number(seg.value) || 0,
    pct: total.value ? Math.round(((Number(seg.value) || 0) / total.value) * 100) : 0,
  })),
)
</script>

<template>
  <div class="rf-donut-wrap flex flex-col items-center gap-6 sm:flex-row">
    <div
      class="rf-donut relative shrink-0 rounded-full p-1 shadow-2xl shadow-indigo-200/40"
      :style="{ width: `${size}px`, height: `${size}px` }"
    >
      <div
        class="h-full w-full rounded-full transition-all duration-1000 ease-out"
        :style="donutStyle"
      />
      <div
        class="absolute inset-0 m-auto flex flex-col items-center justify-center rounded-full bg-white shadow-inner"
        :style="{ width: `${size * 0.62}px`, height: `${size * 0.62}px` }"
      >
        <span class="font-display text-4xl font-black tabular-nums tracking-tight text-slate-900">{{ total }}</span>
        <span class="mt-0.5 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">Araç</span>
      </div>
    </div>

    <ul class="w-full max-w-xs space-y-3">
      <li
        v-for="item in legend"
        :key="item.label"
        class="flex items-center gap-3 rounded-2xl bg-white/60 px-4 py-3 shadow-sm ring-1 ring-slate-100 backdrop-blur-sm"
      >
        <span
          class="h-3.5 w-3.5 shrink-0 rounded-full shadow-sm ring-2 ring-white"
          :style="{ backgroundColor: item.color }"
        />
        <span class="flex-1 text-sm font-semibold text-slate-700">{{ item.label }}</span>
        <span class="font-display text-sm font-black tabular-nums text-slate-900">{{ item.value }}</span>
        <span class="w-10 text-right text-xs font-bold tabular-nums text-slate-400">{{ item.pct }}%</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.rf-donut {
  animation: rf-donut-in 0.8s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes rf-donut-in {
  from {
    opacity: 0;
    transform: scale(0.85) rotate(-8deg);
  }
  to {
    opacity: 1;
    transform: scale(1) rotate(0);
  }
}
</style>
