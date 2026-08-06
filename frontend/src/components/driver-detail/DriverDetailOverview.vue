<script setup>
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRentalWorkflowStore } from '../../stores/rentalWorkflowStore.js'
import { useRentalStore } from '../../stores/rentalStore.js'
import { formatTL, formatNumber } from '../../utils/format.js'
import { getApiErrorMessage } from '../../utils/apiError.js'

const props = defineProps({
  driver: { type: Object, required: true },
})
const emit = defineEmits(['go-rental', 'rented'])

const workflow = useRentalWorkflowStore()
const rentalStore = useRentalStore()
const { readyForDriverPick, vehicleLabel, agreedPrice, pickupDate, dropoffDate } = storeToRefs(workflow)

const risk = computed(() => props.driver?.risk ?? null)
const profile = computed(() => props.driver?.profile_summary ?? null)
const filteredVehicles = computed(() => risk.value?.uygun_araclar ?? [])
const rental = computed(() => props.driver?.active_rental ?? null)

const canAutoRent = computed(() =>
  readyForDriverPick.value
  && !rental.value
  && !props.driver?.is_blacklisted
  && risk.value?.onaylandi
  && (!workflow.vehicleId || filteredVehicles.value.some((v) => v.vehicle_id === workflow.vehicleId)),
)

const autoRentError = ref('')
const autoRenting = ref(false)

function addDays(base, days) {
  const d = new Date(base)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

async function autoRent() {
  if (!props.driver || !canAutoRent.value) return
  autoRentError.value = ''
  autoRenting.value = true
  workflow.attachDriver(props.driver)
  try {
    await rentalStore.createRental({
      driver_id: props.driver.id,
      vehicle_id: workflow.vehicleId,
      pickup_date: workflow.pickupDate,
      dropoff_date: workflow.dropoffDate,
      daily_rate: workflow.agreedDailyRate ?? null,
      deposit_amount: workflow.depositAmount ?? null,
    })
    workflow.clear()
    emit('rented')
  } catch (err) {
    autoRentError.value = getApiErrorMessage(err, 'Otomatik kiralama yapılamadı.')
  } finally {
    autoRenting.value = false
  }
}

function manualRent() {
  if (!props.driver) return
  workflow.attachDriver(props.driver)
  if (!workflow.vehicleId && filteredVehicles.value.length) {
    const v = filteredVehicles.value[0]
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
      agreedDailyRate: workflow.agreedDailyRate,
      pickupDate: addDays(new Date(), 1),
      dropoffDate: addDays(new Date(), 4),
    })
  }
  emit('go-rental')
}
</script>

<template>
  <div class="space-y-6">
    <section
      v-if="canAutoRent"
      class="rounded-xl border-2 border-brand-300 bg-brand-50 p-5"
    >
      <h3 class="text-base font-black text-brand-900">Otomatik Kiralama</h3>
      <p class="mt-1 text-sm text-brand-800">
        {{ vehicleLabel }}
        <span v-if="agreedPrice != null">
          · {{ formatTL(agreedPrice, { decimals: true }) }}
        </span>
        <span v-if="pickupDate && dropoffDate" class="block text-xs text-brand-700/80">
          {{ pickupDate }} → {{ dropoffDate }}
        </span>
      </p>
      <p v-if="autoRentError" class="mt-2 text-sm text-rose-700">{{ autoRentError }}</p>
      <div class="mt-4 flex flex-wrap gap-2">
        <button type="button" class="rf-btn-primary" :disabled="autoRenting" @click="autoRent">
          {{ autoRenting ? 'Atanıyor…' : 'Otomatik Kiralama Yap' }}
        </button>
        <button type="button" class="rf-btn-ghost" @click="manualRent">
          Kiralama Sayfasında Düzenle
        </button>
      </div>
    </section>

    <section v-else-if="readyForDriverPick && rental" class="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
      Bu sürücünün zaten aktif kiralaması var.
    </section>

    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-3 text-sm font-bold uppercase tracking-wider text-slate-500">Kişisel Bilgiler</h3>
      <dl class="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
        <div><dt class="text-slate-500">Yaş</dt><dd class="font-semibold">{{ driver.age }}</dd></div>
        <div><dt class="text-slate-500">Cinsiyet</dt><dd class="font-semibold">{{ driver.gender_display }}</dd></div>
        <div><dt class="text-slate-500">Telefon</dt><dd class="font-semibold">{{ driver.phone }}</dd></div>
        <div><dt class="text-slate-500">E-posta</dt><dd class="font-semibold truncate">{{ driver.email || '—' }}</dd></div>
        <div><dt class="text-slate-500">Ehliyet</dt><dd class="font-semibold">{{ driver.license_class }} · {{ driver.license_number }}</dd></div>
        <div><dt class="text-slate-500">Şehir</dt><dd class="font-semibold">{{ driver.city }}</dd></div>
        <div v-if="profile?.occupation"><dt class="text-slate-500">Meslek</dt><dd class="font-semibold">{{ profile.occupation }}</dd></div>
        <div v-if="profile?.monthly_income"><dt class="text-slate-500">Aylık gelir</dt><dd class="font-semibold">{{ formatTL(profile.monthly_income) }}</dd></div>
        <div v-if="profile?.findeks_score"><dt class="text-slate-500">Findeks</dt><dd class="font-semibold">{{ profile.findeks_score }}</dd></div>
      </dl>
    </section>

    <section v-if="rental" class="rounded-xl border border-blue-200 bg-blue-50 p-5">
      <h3 class="mb-2 text-sm font-bold text-blue-800">Aktif Kiraladığı Araç</h3>
      <p class="font-bold text-slate-900">{{ rental.plate_number }} — {{ rental.brand_model }}</p>
      <p class="mt-1 text-sm text-slate-600">{{ formatNumber(rental.current_km) }} km</p>
    </section>
  </div>
</template>
