<script setup>
import { onMounted, ref, computed } from 'vue'
import { useAuthStore } from './stores/authStore.js'
import LoginView from './views/LoginView.vue'
import Dashboard from './views/Dashboard.vue'
import AIChatbot from './components/AIChatbot.vue'

const auth = useAuthStore()
const booting = ref(true)

onMounted(async () => {
  await auth.bootstrap()
  booting.value = false
})

const showChatbot = computed(() => auth.isFleetManager)
</script>

<template>
  <div v-if="booting" class="grid min-h-screen place-items-center bg-slate-50">
    <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
  </div>
  <LoginView v-else-if="!auth.isAuthenticated" />
  <template v-else>
    <Dashboard />
    <AIChatbot v-if="showChatbot" />
  </template>
</template>
