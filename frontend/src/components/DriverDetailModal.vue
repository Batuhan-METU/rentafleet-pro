<script setup>
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { useDriverStore } from '../stores/driverStore.js'

const props = defineProps({
  driverId: { type: Number, required: true },
})
const emit = defineEmits(['close'])

const store = useDriverStore()
const { selectedDriver, rentalHistory, detailLoading } = storeToRefs(store)

const driver = computed(() => selectedDriver.value)
const score = computed(() => driver.value?.surus_skoru ?? null)
const summary = computed(() => driver.value?.skor_ozeti ?? null)
const rental = computed(() => driver.value?.aktif_kiralama ?? null)

const scoreTheme = computed(() => {
  const value = score.value
  if (value === null) return { border: 'border-slate-200', text: 'text-slate-400', soft: 'bg-slate-50 text-slate-500' }
  if (value > 80) return { border: 'border-emerald-500', text: 'text-emerald-600', soft: 'bg-emerald-50 text-emerald-700' }
  if (value >= 70) return { border: 'border-amber-500', text: 'text-amber-600', soft: 'bg-amber-50 text-amber-700' }
  return { border: 'border-red-500', text: 'text-red-600', soft: 'bg-red-50 text-red-700' }
})

function close() {
  emit('close')
}

function onKeydown(event) {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  store.fetchDriverDetail(props.driverId)
  document.addEventListener('keydown', onKeydown)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
  store.clearSelectedDriver()
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="close">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"></div>

      <div class="relative z-10 flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <header class="flex items-start justify-between gap-4 border-b border-slate-200 bg-slate-50 px-6 py-4">
          <div>
            <h2 class="text-lg font-bold text-slate-900">{{ driver?.ad_soyad ?? 'Sürücü Profili' }}</h2>
            <p class="text-xs text-slate-500">Kiralama kararı için sürüş skoru ve geçmiş</p>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-200" aria-label="Kapat" @click="close">✕</button>
        </header>

        <div class="flex-1 overflow-y-auto px-6 py-6">
          <div v-if="detailLoading" class="grid place-items-center py-16">
            <div class="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
          </div>

          <div v-else-if="driver" class="space-y-6">
            <!-- Profil -->
            <section class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-3 text-sm font-bold uppercase tracking-wider text-slate-500">Kişisel Bilgiler</h3>
              <dl class="grid grid-cols-2 gap-3 text-sm">
                <div><dt class="text-slate-500">Yaş</dt><dd class="font-semibold">{{ driver.yas }}</dd></div>
                <div><dt class="text-slate-500">Cinsiyet</dt><dd class="font-semibold">{{ driver.cinsiyet }}</dd></div>
                <div><dt class="text-slate-500">Telefon</dt><dd class="font-semibold">{{ driver.phone }}</dd></div>
                <div><dt class="text-slate-500">E-posta</dt><dd class="font-semibold truncate">{{ driver.email || '—' }}</dd></div>
                <div><dt class="text-slate-500">Ehliyet</dt><dd class="font-semibold">{{ driver.license_class }}</dd></div>
                <div><dt class="text-slate-500">Şehir</dt><dd class="font-semibold">{{ driver.city }}</dd></div>
              </dl>
            </section>

            <!-- Skor -->
            <section class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-4 text-sm font-bold uppercase tracking-wider text-slate-500">Sürüş Skoru</h3>
              <div class="flex items-center gap-5">
                <div class="grid h-28 w-28 place-items-center rounded-full border-8" :class="scoreTheme.border">
                  <p class="text-3xl font-extrabold" :class="scoreTheme.text">{{ score }}</p>
                </div>
                <div class="flex-1 space-y-2 text-sm">
                  <div class="flex justify-between rounded-lg bg-slate-50 px-3 py-2">
                    <span>Hız ihlali</span><b>{{ summary?.toplam_hiz_ihlali ?? 0 }}</b>
                  </div>
                  <div class="flex justify-between rounded-lg bg-slate-50 px-3 py-2">
                    <span>Ani fren</span><b>{{ summary?.toplam_ani_fren ?? 0 }}</b>
                  </div>
                  <div class="flex justify-between rounded-lg bg-slate-50 px-3 py-2">
                    <span>Ani hızlanma</span><b>{{ summary?.toplam_ani_hizlanma ?? 0 }}</b>
                  </div>
                  <p class="rounded-lg px-3 py-2 text-sm font-semibold" :class="scoreTheme.soft">
                    {{ driver.surus_yorumu }}
                  </p>
                </div>
              </div>
            </section>

            <!-- Aktif kiralama -->
            <section v-if="rental" class="rounded-xl border border-blue-200 bg-blue-50 p-5">
              <h3 class="mb-2 text-sm font-bold text-blue-800">Aktif Kiraladığı Araç</h3>
              <p class="font-bold text-slate-900">{{ rental.plaka }} — {{ rental.marka_model }}</p>
              <p class="mt-1 text-sm text-slate-600">{{ rental.guncel_km?.toLocaleString('tr-TR') }} km</p>
              <p v-if="rental.enlem" class="mt-1 text-xs text-slate-500">
                Konum: {{ rental.enlem }}, {{ rental.boylam }}
              </p>
            </section>

            <!-- Geçmiş -->
            <section class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-3 text-sm font-bold uppercase tracking-wider text-slate-500">Kiralama Geçmişi</h3>
              <ul v-if="rentalHistory.length" class="space-y-2">
                <li v-for="r in rentalHistory" :key="r.id" class="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                  <span class="font-semibold">{{ r.plaka }}</span> · {{ r.marka_model }}
                  <span class="ml-2 text-xs text-slate-500">{{ r.durum }}</span>
                </li>
              </ul>
              <p v-else class="text-sm text-slate-500">Kayıt yok.</p>
            </section>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
