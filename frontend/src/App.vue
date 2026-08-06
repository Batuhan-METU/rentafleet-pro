<script setup>
import { onMounted, ref, computed, watch, defineAsyncComponent } from 'vue'
import { useAuthStore } from './stores/authStore.js'
import { useBrandingStore } from './stores/brandingStore.js'
import { useVehicleMarketStore } from './stores/vehicleMarketStore.js'
import { syncCompanySlugFromHost } from './utils/company.js'
import LoginView from './views/LoginView.vue'
import Workspace from './views/Workspace.vue'
import ErrorBoundary from './components/ErrorBoundary.vue'

// Yalnızca filo yöneticileri için gösterilir — sohbet açılana kadar hiç
// yüklenmesin diye tembel içe aktarılır (bkz. audit bulgusu #34).
const AIChatbot = defineAsyncComponent(() => import('./components/AIChatbot.vue'))

const auth = useAuthStore()
const branding = useBrandingStore()
const vehicleMarketStore = useVehicleMarketStore()
const booting = ref(true)

onMounted(async () => {
  auth.init()
  syncCompanySlugFromHost()
  await branding.fetchBranding()
  await auth.bootstrap()
  if (auth.user) branding.applyFromUser(auth.user)
  booting.value = false
})

// Fiyatlandırma ekranının varsayılan (yarın + 3 gün) piyasa verisini,
// kullanıcı henüz Fiyatlandırma'ya girmeden, giriş yapar yapmaz arka
// planda ısıtmaya başlar — hem oturum geri yüklendiğinde hem taze
// girişte tetiklensin diye auth durumu izlenir (tek seferlik, bkz.
// vehicleStore.prefetchDefaultMarketWindow).
watch(
  () => auth.isAuthenticated && auth.isFleetManager,
  (ready) => {
    if (ready) vehicleMarketStore.prefetchDefaultMarketWindow()
  },
)

const showChatbot = computed(() => auth.isFleetManager)
</script>

<template>
  <div v-if="booting" class="rf-ambient grid min-h-screen place-items-center">
    <div class="rf-glass rounded-3xl p-8">
      <div class="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-white/40 border-t-brand-600" />
      <p class="mt-4 text-sm font-semibold text-slate-600">Yükleniyor…</p>
    </div>
  </div>
  <LoginView v-else-if="!auth.isAuthenticated" />
  <template v-else>
    <ErrorBoundary>
      <Workspace />
      <AIChatbot v-if="showChatbot" />
    </ErrorBoundary>
  </template>
</template>
