<script setup>
defineProps({
  title: { type: String, default: 'Yükleniyor' },
  subtitle: { type: String, default: 'Sayfa hazırlanıyor…' },
})
</script>

<template>
  <Teleport to="body">
    <div class="rf-nav-overlay fixed inset-0 z-[200] flex items-center justify-center">
      <div class="absolute inset-0 bg-slate-900/40 backdrop-blur-md" />

      <div class="rf-nav-overlay-card relative mx-4 w-full max-w-sm overflow-hidden rounded-2xl bg-white p-8 shadow-2xl">
        <div class="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-violet-400/20 blur-2xl" />
        <div class="pointer-events-none absolute -bottom-10 -left-6 h-28 w-28 rounded-full bg-cyan-400/20 blur-2xl" />

        <div class="relative flex flex-col items-center text-center">
          <div class="rf-nav-spinner mb-6 h-14 w-14 rounded-full border-[3px] border-slate-100 border-t-violet-500" />

          <p class="text-lg font-bold text-slate-900">{{ title }}</p>
          <p class="mt-1 text-sm text-slate-500">{{ subtitle }}</p>

          <div class="rf-nav-progress mt-6 h-1 w-full overflow-hidden rounded-full bg-slate-100">
            <div class="rf-nav-progress-bar h-full rounded-full bg-gradient-to-r from-violet-500 via-cyan-400 to-emerald-400" />
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.rf-nav-overlay {
  animation: rf-overlay-in 0.25s ease-out;
}

.rf-nav-overlay-card {
  animation: rf-card-in 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.rf-nav-spinner {
  animation: rf-spin 0.9s linear infinite;
}

.rf-nav-progress-bar {
  animation: rf-progress 1s ease-in-out forwards;
  transform-origin: left;
  transform: scaleX(0);
}

@keyframes rf-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes rf-card-in {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes rf-spin {
  to { transform: rotate(360deg); }
}

@keyframes rf-progress {
  to { transform: scaleX(1); }
}
</style>
