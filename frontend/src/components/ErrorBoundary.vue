<script setup>
// Global hata sınırı — audit'te bulunan "hiçbir onErrorCaptured/errorHandler
// yok" boşluğunu kapatır. Sarmaladığı alt ağaçta (App.vue'de <Workspace/>
// etrafında) yakalanmamış bir render/lifecycle hatası artık sessiz beyaz
// ekrana değil, "sayfayı yenile" seçeneği sunan bir mesaja düşer.
import { onErrorCaptured, ref } from 'vue'

const error = ref(null)

onErrorCaptured((err, instance, info) => {
  console.error('[ErrorBoundary] Yakalanmamış hata:', err, info)
  error.value = err
  return false // hata burada durur, App.vue'nin üstüne taşınmaz
})

function reload() {
  window.location.reload()
}
</script>

<template>
  <div v-if="error" class="rf-ambient grid min-h-screen place-items-center p-6">
    <div class="rf-glass-strong max-w-md rounded-3xl p-8 text-center">
      <div class="mx-auto grid h-14 w-14 place-items-center rounded-full bg-red-100 text-2xl font-bold text-red-600">!</div>
      <p class="mt-4 text-lg font-bold text-slate-800">Bir şeyler ters gitti</p>
      <p class="mt-1 text-sm text-slate-500">
        Sayfa beklenmedik bir hatayla karşılaştı. Sayfayı yenilemeyi deneyin;
        sorun devam ederse ekibe bildirin.
      </p>
      <button type="button" class="rf-btn-primary mt-5" @click="reload">Sayfayı Yenile</button>
    </div>
  </div>
  <slot v-else />
</template>
