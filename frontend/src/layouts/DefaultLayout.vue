<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { useAuthStore } from '../stores/authStore.js'
import { useUiStore } from '../stores/uiStore.js'
import AppSidebar from '../components/AppSidebar.vue'

const auth = useAuthStore()
const ui = useUiStore()
const { activeView } = storeToRefs(ui)

const PAGE_META = {
  overview: { title: 'Ev', subtitle: '' },
  vehicles: { title: 'Araçlar', subtitle: 'Tüm filo araçlarını görüntüleyin ve filtreleyin' },
  drivers: { title: 'Sürücüler', subtitle: 'Müşteri sürücü profilleri, skorlar ve kiralama geçmişi' },
  live: { title: 'Canlı Takip', subtitle: 'Araçlarınızı harita üzerinde gerçek zamanlı izleyin' },
  maintenance: { title: 'Bakım Merkezi', subtitle: 'Öngörücü bakım uyarıları ve araç yıpranma durumu' },
  pricing: { title: 'Fiyatlandırma', subtitle: 'Piyasa fiyatları + maliyet tabanlı fiyat önerisi' },
  reservations: { title: 'Rezervasyonlar', subtitle: 'Araç–sürücü atamaları ve kiralama kayıtları' },
  settings: { title: 'Ayarlar', subtitle: 'Şirket profili, marka ve personel yönetimi' },
}

const pageMeta = computed(() => PAGE_META[activeView.value] ?? PAGE_META.overview)

function navigate(view) {
  ui.navigate(view, { isFleetManager: auth.isFleetManager })
}

function onHashChange() {
  ui.onHashChange(auth.isFleetManager)
}

const emit = defineEmits(['logout'])

function logout() {
  emit('logout')
}

onMounted(() => {
  ui.initNavigation(auth.isFleetManager)
  window.addEventListener('hashchange', onHashChange)
})

onBeforeUnmount(() => {
  window.removeEventListener('hashchange', onHashChange)
})
</script>

<template>
  <div class="rf-ambient flex h-screen overflow-hidden">
    <AppSidebar :active-view="activeView" @navigate="navigate" @logout="logout" />

    <div class="flex min-w-0 flex-1 flex-col overflow-hidden">
      <header class="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-4">
        <div class="min-w-0">
          <h1 class="rf-section-title leading-tight">{{ pageMeta.title }}</h1>
          <p v-if="pageMeta.subtitle" class="rf-section-sub mt-1 leading-snug">{{ pageMeta.subtitle }}</p>
        </div>
        <div class="flex flex-wrap items-center justify-end gap-3">
          <slot name="actions" :active-view="activeView" :navigate="navigate" />
        </div>
      </header>

      <main class="flex-1 overflow-y-auto p-6">
        <slot :active-view="activeView" :navigate="navigate" />
      </main>
    </div>
  </div>
</template>
