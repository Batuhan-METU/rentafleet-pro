<script setup>
// Global bildirim zili — DefaultLayout.vue header'ında, her sayfada görünür.
// Tek bildirim türü: teslim tarihi geçmiş ama henüz teslim alınmamış aktif
// kiralamalar (Rental.is_overdue). Ayrı bir "okundu/kapatıldı" durumu YOK —
// bir kiralama uzatılıp/teslim alınıp is_overdue false olduğu an, sinyal
// zaten rentalStore.overdueRentals'tan kendiliğinden düşer.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRentalStore } from '../stores/rentalStore.js'
import ExtendRentalModal from './ExtendRentalModal.vue'
import ReturnVehicleModal from './ReturnVehicleModal.vue'
import { formatDate } from '../utils/format.js'
import { useClickOutside } from '../composables/useClickOutside.js'

const REFRESH_INTERVAL_MS = 2 * 60 * 1000

const rentalStore = useRentalStore()

const open = ref(false)
const rootEl = ref(null)
const extendTarget = ref(null)
const returnTarget = ref(null)

const overdueRentals = computed(() => rentalStore.overdueRentals)
const count = computed(() => rentalStore.summary.active_overdue ?? 0)

function toggle() {
  open.value = !open.value
}

useClickOutside(rootEl, () => {
  open.value = false
})

function openExtendModal(rental) {
  extendTarget.value = rental
}
function closeExtendModal() {
  extendTarget.value = null
}
function onRentalExtended() {
  rentalStore.fetchRentals()
}

function openReturnModal(rental) {
  returnTarget.value = rental
}
function closeReturnModal() {
  returnTarget.value = null
}
function onVehicleReturned() {
  rentalStore.fetchRentals()
}

let refreshTimer = null

onMounted(() => {
  rentalStore.ensureRentalsLoaded()
  refreshTimer = window.setInterval(() => rentalStore.fetchRentals(), REFRESH_INTERVAL_MS)
})

onBeforeUnmount(() => {
  clearInterval(refreshTimer)
})
</script>

<template>
  <div ref="rootEl" class="relative">
    <button
      type="button"
      class="relative grid h-10 w-10 place-items-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-700"
      title="Bildirimler"
      @click="toggle"
    >
      <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
        <path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
      </svg>
      <span
        v-if="count > 0"
        class="absolute right-1 top-1 grid h-4 min-w-[1rem] place-items-center rounded-full bg-rose-600 px-1 text-[10px] font-black leading-none text-white"
      >
        {{ count }}
      </span>
    </button>

    <div
      v-if="open"
      class="absolute right-0 z-40 mt-2 w-80 rounded-2xl border border-slate-200 bg-white shadow-2xl"
    >
      <div class="border-b border-slate-100 px-4 py-3">
        <p class="text-sm font-bold text-slate-800">Bildirimler</p>
        <p class="text-xs text-slate-400">Teslim tarihi geçmiş, henüz teslim alınmamış kiralamalar</p>
      </div>

      <div v-if="!overdueRentals.length" class="px-4 py-8 text-center text-sm text-slate-400">
        Bekleyen bildirim yok.
      </div>

      <ul v-else class="max-h-96 divide-y divide-slate-100 overflow-y-auto">
        <li v-for="r in overdueRentals" :key="r.id" class="px-4 py-3">
          <p class="text-sm font-bold text-slate-800">{{ r.driver_name }}</p>
          <p class="text-xs text-slate-500">{{ r.plate_number }} — {{ r.brand_model }}</p>
          <p class="mt-0.5 text-xs font-semibold text-rose-600">Bitiş: {{ formatDate(r.ended_at) }}</p>
          <div class="mt-2 flex gap-2">
            <button
              type="button"
              class="cursor-pointer rounded-lg border border-sky-200 bg-sky-50 px-2.5 py-1.5 text-xs font-bold text-sky-700 transition-colors hover:bg-sky-100"
              @click="openExtendModal(r)"
            >
              Uzat
            </button>
            <button
              type="button"
              class="cursor-pointer rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-xs font-bold text-emerald-700 transition-colors hover:bg-emerald-100"
              @click="openReturnModal(r)"
            >
              Teslim Al
            </button>
          </div>
        </li>
      </ul>
    </div>

    <ExtendRentalModal
      v-if="extendTarget"
      :rental="extendTarget"
      @close="closeExtendModal"
      @extended="onRentalExtended"
    />

    <ReturnVehicleModal
      v-if="returnTarget"
      :rental="returnTarget"
      @close="closeReturnModal"
      @returned="onVehicleReturned"
    />
  </div>
</template>
