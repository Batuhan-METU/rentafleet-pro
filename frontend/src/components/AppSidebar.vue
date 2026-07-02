<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../stores/authStore.js'

defineProps({
  activeView: { type: String, required: true },
})
const emit = defineEmits(['navigate', 'logout'])

const auth = useAuthStore()

const allNavItems = [
  { id: 'overview', label: 'Genel Bakış', managerOnly: true, icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
  { id: 'vehicles', label: 'Araçlar', icon: 'M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1' },
  { id: 'drivers', label: 'Sürücüler', icon: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z' },
  { id: 'live', label: 'Canlı Takip', icon: 'M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z M15 11a3 3 0 11-6 0 3 3 0 016 0z' },
  { id: 'maintenance', label: 'Bakım Merkezi', icon: 'M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233c.55-.164 1.163-.188 1.743-.14a4.5 4.5 0 004.486-6.336l-3.276 3.277a3.004 3.004 0 01-2.25-2.25l3.276-3.276a4.5 4.5 0 00-6.336 4.486c.091 1.076-.071 2.264-.904 2.95l-.102.085m-1.745 1.437L5.909 7.5H4.5L2.25 3.75l1.5-1.5L7.5 4.5v1.409l4.26 4.26' },
  { id: 'pricing', label: 'Fiyatlandırma', managerOnly: true, icon: 'M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z' },
]

const navItems = computed(() =>
  allNavItems.filter((item) => !item.managerOnly || auth.isFleetManager),
)

const comingSoon = [
  { label: 'Telemetri', icon: 'M13 10V3L4 14h7v7l9-11h-7z' },
  { label: 'Ayarlar', icon: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z' },
]
</script>

<template>
  <aside class="flex h-full w-64 flex-col bg-slate-900 text-slate-300">
    <!-- Marka -->
    <div class="flex items-center gap-3 px-5 py-5 border-b border-white/10">
      <div class="grid h-10 w-10 place-items-center rounded-xl bg-brand-600 font-extrabold text-white">
        RF
      </div>
      <div class="leading-tight">
        <p class="text-sm font-bold text-white">RentA-Fleet <span class="font-normal text-slate-400">PRO</span></p>
        <p class="text-xs text-slate-400">Filo Yönetimi</p>
      </div>
    </div>

    <!-- Navigasyon -->
    <nav class="flex-1 space-y-1 px-3 py-4">
      <p class="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Menü</p>
      <button
        v-for="item in navItems"
        :key="item.id"
        type="button"
        class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors"
        :class="activeView === item.id
          ? 'bg-brand-600 text-white shadow-sm'
          : 'text-slate-300 hover:bg-white/5 hover:text-white'"
        @click="emit('navigate', item.id)"
      >
        <svg class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
          <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
        </svg>
        {{ item.label }}
      </button>

      <p class="px-3 pt-5 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Yakında</p>
      <div
        v-for="item in comingSoon"
        :key="item.label"
        class="flex w-full cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-500"
      >
        <svg class="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
          <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
        </svg>
        {{ item.label }}
      </div>
    </nav>

    <!-- Kullanıcı -->
    <div class="border-t border-white/10 px-5 py-4">
      <div class="flex items-center gap-3">
        <div class="grid h-9 w-9 place-items-center rounded-full bg-slate-700 text-sm font-semibold text-white">
          {{ auth.initials }}
        </div>
        <div class="min-w-0 flex-1 leading-tight">
          <p class="truncate text-sm font-medium text-white">{{ auth.displayName }}</p>
          <p class="truncate text-xs text-slate-400">{{ auth.roleLabel }}</p>
        </div>
      </div>
      <button
        type="button"
        class="mt-3 w-full rounded-lg border border-white/10 px-3 py-2 text-xs font-medium text-slate-400 transition hover:bg-white/5 hover:text-white"
        @click="emit('logout')"
      >
        Çıkış Yap
      </button>
    </div>
  </aside>
</template>
