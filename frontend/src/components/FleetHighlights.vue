<script setup>
/** BandLab tarzı 3 sütunlu özellik şeridi — filo yetenekleri. */
const features = [
  {
    title: 'Hızlı',
    desc: 'Canlı harita ve anlık doluluk metrikleriyle filonuzu saniyeler içinde görün.',
    icon: 'M13 5l7 7-7 7M5 5l7 7-7 7',
  },
  {
    title: 'Akıllı',
    desc: 'AI danışman ve piyasa analizi ile fiyat ve bakım kararlarını veriye dayandırın.',
    icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
  },
  {
    title: 'Güvenli',
    desc: 'Sürüş skoru, anomali tespiti ve kiracı izolasyonu ile verileriniz korunur.',
    icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
  },
]
</script>

<template>
  <section class="rf-feature-band relative mt-8">
    <div class="grid grid-cols-1 gap-8 md:grid-cols-3 md:gap-6">
      <div
        v-for="item in features"
        :key="item.title"
        class="group flex flex-col items-center text-center"
      >
        <span class="rf-icon-ring rf-interactive mb-5">
          <svg class="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.6">
            <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
          </svg>
        </span>
        <h3 class="text-lg font-black tracking-tight text-slate-900">{{ item.title }}</h3>
        <p class="mt-2 max-w-xs text-sm leading-relaxed text-slate-500/90">{{ item.desc }}</p>
      </div>
    </div>
  </section>
</template>
