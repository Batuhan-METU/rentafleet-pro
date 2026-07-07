<script setup>
import { onMounted, ref, computed } from 'vue'
import { useAuthStore } from './stores/authStore.js'
import { useBrandingStore } from './stores/brandingStore.js'
import { syncTenantSlugFromHost } from './utils/tenant.js'
import LoginView from './views/LoginView.vue'
import Dashboard from './views/Dashboard.vue'
import AIChatbot from './components/AIChatbot.vue'

const auth = useAuthStore()
const branding = useBrandingStore()
const booting = ref(true)

onMounted(async () => {
  auth.init()
  syncTenantSlugFromHost()
  await branding.fetchBranding()
  await auth.bootstrap()
  if (auth.user) branding.applyFromUser(auth.user)
  booting.value = false
})

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
    <Dashboard />
    <AIChatbot v-if="showChatbot" />
  </template>
</template>
