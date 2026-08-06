<script setup>
// Sürücü ve aracı elle seçerek kiralama oluşturma modalı — eskiden
// Kiralamalar sayfasında açılır/kapanır bir kart olan "Manuel Kiralama"
// bölümünün yerini alır; artık sağ üstteki "Kiralama Yap" butonuyla açılır.
import { computed, ref } from 'vue'
import { useRentalStore } from '../stores/rentalStore.js'
import { useVehicleStore } from '../stores/vehicleStore.js'
import { useDriverStore } from '../stores/driverStore.js'
import DatePicker from './vehicle-form/DatePicker.vue'
import TimePicker from './vehicle-form/TimePicker.vue'
import { formatTL } from '../utils/format.js'
import { getApiErrorMessage } from '../utils/apiError.js'

const emit = defineEmits(['close', 'created'])

const rentalStore = useRentalStore()
const vehicleStore = useVehicleStore()
const driverStore = useDriverStore()

function addDays(base, days) {
  const d = new Date(base)
  d.setDate(d.getDate() + days)
  return d.toISOString().slice(0, 10)
}

const form = ref({
  driverId: '',
  vehicleId: '',
  pickupDate: addDays(new Date(), 1),
  dropoffDate: addDays(new Date(), 4),
  pickupTime: '10:00',
  dropoffTime: '10:00',
  dailyRate: '',
})

const formError = ref('')

const availableVehicles = computed(() =>
  vehicleStore.vehicles.filter((v) => v.status === 'AVAILABLE'),
)

function parsePrice(raw) {
  if (!raw) return null
  const n = Number(String(raw).replace(/\s/g, '').replace(/\./g, '').replace(',', '.'))
  return Number.isNaN(n) || n <= 0 ? null : n
}

function daysBetween(pickup, dropoff) {
  if (!pickup || !dropoff) return null
  const diff = (new Date(dropoff) - new Date(pickup)) / (1000 * 60 * 60 * 24)
  return diff > 0 ? Math.round(diff) : null
}

const formTotal = computed(() => {
  const rate = parsePrice(form.value.dailyRate)
  const days = daysBetween(form.value.pickupDate, form.value.dropoffDate)
  return rate && days ? rate * days : null
})

async function submit() {
  formError.value = ''

  if (!form.value.driverId || !form.value.vehicleId) {
    formError.value = 'Sürücü ve araç seçilmelidir.'
    return
  }
  if (!form.value.pickupDate || !form.value.dropoffDate) {
    formError.value = 'Alış ve bırakış tarihlerini girin.'
    return
  }
  if (form.value.dropoffDate <= form.value.pickupDate) {
    formError.value = 'Bırakış tarihi alış tarihinden sonra olmalıdır.'
    return
  }

  try {
    await rentalStore.createRental({
      driver_id: Number(form.value.driverId),
      vehicle_id: Number(form.value.vehicleId),
      pickup_date: form.value.pickupDate,
      dropoff_date: form.value.dropoffDate,
      pickup_time: form.value.pickupTime,
      dropoff_time: form.value.dropoffTime,
      daily_rate: parsePrice(form.value.dailyRate),
    })
    emit('created')
  } catch (err) {
    formError.value = getApiErrorMessage(err, 'Kiralama oluşturulamadı.')
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-6" @click.self="emit('close')" @keydown="onKeydown">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" />
      <div class="relative my-4 w-full max-w-2xl overflow-hidden rounded-3xl rf-glass-strong shadow-2xl">
        <div class="rf-accent-bar" />
        <header class="flex items-center justify-between border-b border-white/30 px-6 py-4">
          <div>
            <h2 class="text-lg font-bold text-slate-900">Kiralama Yap</h2>
            <p class="text-sm text-slate-500">Sürücü ve aracı elle seçerek kiralama oluşturun.</p>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-100" @click="emit('close')">✕</button>
        </header>

        <div class="px-6 py-5">
          <div v-if="formError" class="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {{ formError }}
          </div>

          <div class="grid gap-4 sm:grid-cols-2">
            <div>
              <label class="text-xs font-medium text-slate-500">Sürücü</label>
              <select v-model="form.driverId" class="rf-input mt-1">
                <option value="">Seçin…</option>
                <option v-for="d in driverStore.drivers" :key="d.id" :value="d.id">
                  {{ d.full_name }} — {{ d.phone }}
                </option>
              </select>
            </div>
            <div>
              <label class="text-xs font-medium text-slate-500">Araç</label>
              <select v-model="form.vehicleId" class="rf-input mt-1">
                <option value="">Seçin…</option>
                <option v-for="v in availableVehicles" :key="v.id" :value="v.id">
                  {{ v.plate_number }} — {{ v.brand }} {{ v.model }}
                </option>
              </select>
            </div>
            <div>
              <label class="text-xs font-medium text-slate-500">Alış Tarihi</label>
              <div class="mt-1"><DatePicker v-model="form.pickupDate" /></div>
            </div>
            <div>
              <label class="text-xs font-medium text-slate-500">Alış Saati</label>
              <div class="mt-1"><TimePicker v-model="form.pickupTime" /></div>
            </div>
            <div>
              <label class="text-xs font-medium text-slate-500">Bırakış Tarihi</label>
              <div class="mt-1"><DatePicker v-model="form.dropoffDate" /></div>
            </div>
            <div>
              <label class="text-xs font-medium text-slate-500">Bırakış Saati</label>
              <div class="mt-1"><TimePicker v-model="form.dropoffTime" /></div>
            </div>
            <div class="sm:col-span-2">
              <label class="text-xs font-medium text-slate-500">Günlük Fiyat (₺)</label>
              <input v-model="form.dailyRate" type="text" class="rf-input mt-1" placeholder="Opsiyonel" />
              <p v-if="formTotal != null" class="mt-1 text-xs text-slate-500">
                = {{ formatTL(formTotal, { decimals: true }) }} toplam
              </p>
            </div>
          </div>

          <div class="mt-6 flex justify-end gap-3">
            <button type="button" class="rf-btn-ghost" @click="emit('close')">Vazgeç</button>
            <button
              type="button"
              class="rf-btn-primary"
              :disabled="rentalStore.creating"
              @click="submit"
            >
              {{ rentalStore.creating ? 'Kaydediliyor…' : 'Kiralama Oluştur' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
