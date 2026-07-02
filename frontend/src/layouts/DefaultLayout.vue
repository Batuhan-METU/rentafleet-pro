<script setup>
// Uygulama kabuğu (app-shell): sol kenar çubuğu + üst bar + içerik alanı.
import { ref } from 'vue'
import { useAuthStore } from '../stores/authStore.js'
import AppSidebar from '../components/AppSidebar.vue'

const auth = useAuthStore()

const PAGE_META = {
  overview: { title: 'Genel Bakış', subtitle: 'Filonuzu tek ekrandan yönetin' },
  vehicles: { title: 'Araçlar', subtitle: 'Tüm filo araçlarını görüntüleyin ve filtreleyin' },
  drivers: { title: 'Sürücüler', subtitle: 'Müşteri sürücü profilleri, skorlar ve kiralama geçmişi' },
  live: { title: 'Canlı Takip', subtitle: 'Araçlarınızı harita üzerinde gerçek zamanlı izleyin' },
  maintenance: { title: 'Bakım Merkezi', subtitle: 'Öngörücü bakım uyarıları ve araç yıpranma durumu' },
  pricing: { title: 'Fiyatlandırma', subtitle: 'Dinamik yield fiyatlandırma ve talep analizi' },
}

// Operasyon personeli genel bakışa erişemez; varsayılan sekme araçlar.
const activeView = ref(auth.isFleetManager ? 'overview' : 'vehicles')

function navigate(view) {
  activeView.value = view
}

const emit = defineEmits(['logout'])

function logout() {
  emit('logout')
}
</script>

<template>
  <div class="flex h-screen overflow-hidden">
    <AppSidebar :active-view="activeView" @navigate="navigate" @logout="logout" />

    <div class="flex flex-1 flex-col overflow-hidden">
      <header class="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4">
        <div>
          <h1 class="text-xl font-bold text-slate-900">{{ PAGE_META[activeView]?.title }}</h1>
          <p class="text-sm text-slate-500">{{ PAGE_META[activeView]?.subtitle }}</p>
        </div>
        <div class="flex items-center gap-3">
          <slot name="actions" :active-view="activeView" :navigate="navigate" />
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-6">
        <slot :active-view="activeView" :navigate="navigate" />
      </main>
    </div>
  </div>
</template>
