<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useDriverStore } from '../stores/driverStore.js'
import { useVehicleStore } from '../stores/vehicleStore.js'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'
import { useRentalStore } from '../stores/rentalStore.js'
import { formatTL } from '../utils/format.js'
const props = defineProps({
  driverId: { type: Number, required: true },
})
const emit = defineEmits(['close', 'go-reservation', 'reserved'])

const store = useDriverStore()
const vehicleStore = useVehicleStore()
const workflow = useRentalWorkflowStore()
const rentalStore = useRentalStore()
const { selectedDriver, rentalHistory, detailLoading } = storeToRefs(store)
const { readyForDriverPick, vehicleLabel, agreedPrice, pickupDate, dropoffDate } = storeToRefs(workflow)

const showAllVehicles = ref(false)

const driver = computed(() => selectedDriver.value)
const risk = computed(() => driver.value?.risk ?? null)
const profile = computed(() => driver.value?.profil_ozeti ?? null)
const filteredVehicles = computed(() => risk.value?.uygun_araclar ?? [])
const rental = computed(() => driver.value?.aktif_kiralama ?? null)

const allFleetVehicles = computed(() =>
  vehicleStore.vehicles
    .filter((v) => v.status === 'AVAILABLE')
    .map((v) => ({
      vehicle_id: v.id,
      plate_number: v.plate_number,
      brand: v.brand,
      model: v.model,
      tier: v.sinif_etiketi || '—',
      sipp_code: v.sipp_code,
    })),
)

const vehicles = computed(() =>
  showAllVehicles.value ? allFleetVehicles.value : filteredVehicles.value,
)

const canAutoReserve = computed(() =>
  readyForDriverPick.value
  && !rental.value
  && !driver.value?.is_blacklisted,
)

const autoReserveError = ref('')
const autoReserving = ref(false)

function addDays(base, days) {
  const d = new Date(base)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

const riskTone = computed(() => {
  const score = risk.value?.skor
  if (score == null) return { border: 'border-slate-200', text: 'text-slate-400', soft: 'bg-slate-50 text-slate-500' }
  if (score <= 30) return { border: 'border-emerald-500', text: 'text-emerald-600', soft: 'bg-emerald-50 text-emerald-700' }
  if (score <= 60) return { border: 'border-amber-500', text: 'text-amber-600', soft: 'bg-amber-50 text-amber-700' }
  return { border: 'border-red-500', text: 'text-red-600', soft: 'bg-red-50 text-red-700' }
})

function close() {
  emit('close')
}

async function autoReserve() {
  if (!driver.value || !canAutoReserve.value) return
  autoReserveError.value = ''
  autoReserving.value = true
  workflow.attachDriver(driver.value)
  try {
    await rentalStore.createRental({
      driver_id: driver.value.id,
      vehicle_id: workflow.vehicleId,
      pickup_date: workflow.pickupDate,
      dropoff_date: workflow.dropoffDate,
      quoted_total: workflow.agreedPrice ?? null,
      deposit_amount: workflow.depositAmount ?? null,
    })
    workflow.clear()
    emit('reserved')
    close()
  } catch (err) {
    autoReserveError.value = err?.response?.data?.error ?? 'Otomatik rezervasyon yapılamadı.'
  } finally {
    autoReserving.value = false
  }
}

function manualReserve() {
  if (!driver.value) return
  workflow.attachDriver(driver.value)
  if (!workflow.vehicleId && vehicles.value.length) {
    const v = vehicles.value[0]
    workflow.selectVehicle({
      id: v.vehicle_id,
      plate_number: v.plate_number,
      brand: v.brand,
      model: v.model,
    })
  }
  if (!workflow.pickupDate) {
    workflow.setPricing({
      agreedPrice: workflow.agreedPrice,
      pickupDate: addDays(new Date(), 1),
      dropoffDate: addDays(new Date(), 4),
    })
  }
  emit('go-reservation')
  close()
}

function onKeydown(event) {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  store.fetchDriverDetail(props.driverId)
  if (!vehicleStore.vehicles.length) void vehicleStore.fetchVehicles()
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
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" />

      <div class="relative z-10 flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-3xl rf-glass-strong shadow-2xl">
        <div class="rf-accent-bar" />
        <header class="flex items-start justify-between gap-4 border-b border-white/30 px-6 py-4">
          <div>
            <h2 class="text-lg font-bold text-slate-900">{{ driver?.ad_soyad ?? 'Sürücü Profili' }}</h2>
            <p class="text-xs text-slate-500">Kişisel bilgiler, risk skoru ve uygun araçlar</p>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-200" @click="close">✕</button>
        </header>

        <div class="flex-1 overflow-y-auto px-6 py-6">
          <div v-if="detailLoading" class="grid place-items-center py-16">
            <div class="h-12 w-12 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600" />
          </div>

          <div v-else-if="driver" class="space-y-6">
            <!-- Rezervasyon — en üstte, hemen görünsün -->
            <section
              v-if="canAutoReserve"
              class="rounded-xl border-2 border-brand-300 bg-brand-50 p-5"
            >
              <h3 class="text-base font-black text-brand-900">Otomatik Rezervasyon</h3>
              <p class="mt-1 text-sm text-brand-800">
                {{ vehicleLabel }}
                <span v-if="agreedPrice != null">
                  · {{ formatTL(agreedPrice, { decimals: true }) }}
                </span>
                <span v-if="pickupDate && dropoffDate" class="block text-xs text-brand-700/80">
                  {{ pickupDate }} → {{ dropoffDate }}
                </span>
              </p>
              <p v-if="autoReserveError" class="mt-2 text-sm text-rose-700">{{ autoReserveError }}</p>
              <div class="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  class="rf-btn-primary"
                  :disabled="autoReserving"
                  @click="autoReserve"
                >
                  {{ autoReserving ? 'Atanıyor…' : 'Otomatik Rezervasyon Yap' }}
                </button>
                <button type="button" class="rf-btn-ghost" @click="manualReserve">
                  Rezervasyon Sayfasında Düzenle
                </button>
              </div>
            </section>

            <section v-else-if="readyForDriverPick && rental" class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              Bu sürücünün zaten aktif kiralaması var.
            </section>

            <section class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-3 text-sm font-bold uppercase tracking-wider text-slate-500">Kişisel Bilgiler</h3>
              <dl class="grid grid-cols-2 gap-3 text-sm">
                <div><dt class="text-slate-500">Yaş</dt><dd class="font-semibold">{{ driver.yas }}</dd></div>
                <div><dt class="text-slate-500">Cinsiyet</dt><dd class="font-semibold">{{ driver.cinsiyet }}</dd></div>
                <div><dt class="text-slate-500">Telefon</dt><dd class="font-semibold">{{ driver.phone }}</dd></div>
                <div><dt class="text-slate-500">E-posta</dt><dd class="font-semibold truncate">{{ driver.email || '—' }}</dd></div>
                <div><dt class="text-slate-500">Ehliyet</dt><dd class="font-semibold">{{ driver.license_class }} · {{ driver.license_number }}</dd></div>
                <div><dt class="text-slate-500">Şehir</dt><dd class="font-semibold">{{ driver.city }}</dd></div>
                <div v-if="profile?.meslek"><dt class="text-slate-500">Meslek</dt><dd class="font-semibold">{{ profile.meslek }}</dd></div>
                <div v-if="profile?.aylik_gelir"><dt class="text-slate-500">Aylık gelir</dt><dd class="font-semibold">{{ formatTL(profile.aylik_gelir) }}</dd></div>
                <div v-if="profile?.findeks_skoru"><dt class="text-slate-500">Findeks</dt><dd class="font-semibold">{{ profile.findeks_skoru }}</dd></div>
              </dl>
            </section>

            <section class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-4 text-sm font-bold uppercase tracking-wider text-slate-500">Risk Skoru</h3>
              <div v-if="risk" class="flex flex-wrap items-start gap-5">
                <div class="grid h-28 w-28 place-items-center rounded-full border-8" :class="riskTone.border">
                  <p class="text-3xl font-extrabold" :class="riskTone.text">{{ risk.skor ?? '—' }}</p>
                </div>
                <div class="min-w-[12rem] flex-1 space-y-2 text-sm">
                  <p class="rounded-lg px-3 py-2 font-semibold" :class="riskTone.soft">
                    Seviye: {{ risk.seviye_label || '—' }}
                  </p>
                  <p v-if="risk.depozito" class="rounded-lg bg-slate-50 px-3 py-2">
                    Önerilen depozito: <b>{{ formatTL(risk.depozito, { decimals: true }) }}</b>
                  </p>
                  <ul v-if="risk.uyarilar?.length" class="list-disc pl-5 text-amber-700">
                    <li v-for="(w, i) in risk.uyarilar" :key="i">{{ w }}</li>
                  </ul>
                  <ul v-if="risk.blokajlar?.length" class="list-disc pl-5 text-rose-700">
                    <li v-for="(b, i) in risk.blokajlar" :key="i">{{ b }}</li>
                  </ul>
                </div>
              </div>
              <p v-else class="text-sm text-slate-500">Henüz risk değerlendirmesi yapılmamış.</p>
            </section>

            <section class="rounded-xl border border-slate-200 p-5">
              <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 class="text-sm font-bold uppercase tracking-wider text-slate-500">
                  {{ showAllVehicles ? 'Tüm Araçlar' : 'Uygun Araçlar' }}
                </h3>
                <button
                  type="button"
                  class="rounded-full px-3 py-1 text-xs font-bold transition"
                  :class="showAllVehicles
                    ? 'bg-brand-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
                  @click="showAllVehicles = !showAllVehicles"
                >
                  {{ showAllVehicles ? 'Filtreyi Uygula' : 'Filtreyi Kaldır' }}
                </button>
              </div>
              <div v-if="vehicles.length" class="grid gap-3 sm:grid-cols-2">
                <div
                  v-for="vehicle in vehicles"
                  :key="vehicle.vehicle_id"
                  class="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3"
                >
                  <p class="font-black text-slate-900">{{ vehicle.plate_number }}</p>
                  <p class="text-sm text-slate-600">{{ vehicle.brand }} {{ vehicle.model }}</p>
                  <p class="mt-1 text-xs font-semibold text-brand-600">{{ vehicle.tier }} · {{ vehicle.sipp_code }}</p>
                </div>
              </div>
              <p v-else class="text-sm text-slate-500">
                {{ showAllVehicles
                  ? 'Müsait araç bulunamadı.'
                  : (risk?.blokajlar?.length ? 'Risk nedeniyle uygun araç bulunamadı.' : 'Uygun araç listesi boş.') }}
              </p>
            </section>

            <section v-if="rental" class="rounded-xl border border-blue-200 bg-blue-50 p-5">
              <h3 class="mb-2 text-sm font-bold text-blue-800">Aktif Kiraladığı Araç</h3>
              <p class="font-bold text-slate-900">{{ rental.plaka }} — {{ rental.marka_model }}</p>
              <p class="mt-1 text-sm text-slate-600">{{ rental.guncel_km?.toLocaleString('tr-TR') }} km</p>
            </section>

            <section class="rounded-xl border border-slate-200 p-5">
              <h3 class="mb-3 text-sm font-bold uppercase tracking-wider text-slate-500">Kiralama Geçmişi</h3>
              <ul v-if="rentalHistory.length" class="space-y-2">
                <li v-for="r in rentalHistory" :key="r.id" class="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                  <span class="font-semibold">{{ r.plaka }}</span> · {{ r.marka_model }}
                  <span class="ml-2 text-xs text-slate-500">{{ r.durum }}</span>
                </li>
              </ul>
              <p v-else class="text-sm text-slate-500">Henüz kiralama yok.</p>
            </section>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
