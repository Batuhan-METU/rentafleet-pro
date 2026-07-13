<script setup>
// Araç ekleme/düzenleme: künye + gerçek maliyet kalemleri (satış planı sorulmaz).
import { reactive, ref, computed } from 'vue'
import { useFinanceStore } from '../../stores/financeStore.js'

const props = defineProps({
  editVehicle: { type: Object, default: null },
  editProfile: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'cancel'])

const finance = useFinanceStore()
const isEdit = computed(() => !!props.editVehicle)

const FUEL_TYPES = [
  { value: 'GASOLINE', label: 'Benzin' },
  { value: 'DIESEL', label: 'Dizel' },
  { value: 'LPG', label: 'LPG' },
  { value: 'HYBRID', label: 'Hibrit' },
  { value: 'ELECTRIC', label: 'Elektrik' },
]
const TRANSMISSIONS = [
  { value: 'MANUAL', label: 'Manuel' },
  { value: 'AUTOMATIC', label: 'Otomatik' },
  { value: 'SEMI_AUTOMATIC', label: 'Yarı Otomatik' },
]
const BODY_TYPES = [
  { value: 'SEDAN', label: 'Sedan' },
  { value: 'HATCHBACK', label: 'Hatchback' },
  { value: 'STATION_WAGON', label: 'Station Wagon' },
  { value: 'SUV', label: 'SUV' },
  { value: 'CROSSOVER', label: 'Crossover' },
  { value: 'MINIVAN', label: 'Minivan' },
  { value: 'PICKUP', label: 'Pickup' },
  { value: 'VAN', label: 'Panelvan' },
  { value: 'COUPE', label: 'Coupe' },
]
const CONDITIONS = [
  { value: 'NEW', label: 'Sıfır' },
  { value: 'USED', label: 'İkinci El' },
]

const form = reactive({
  plate_number: props.editVehicle?.plate_number ?? '',
  brand: props.editVehicle?.brand ?? '',
  model: props.editVehicle?.model ?? '',
  package: props.editVehicle?.package ?? '',
  production_year: props.editVehicle?.production_year ?? new Date().getFullYear(),
  fuel_type: props.editVehicle?.fuel_type ?? 'GASOLINE',
  transmission: props.editVehicle?.transmission ?? '',
  engine_displacement_cc: props.editVehicle?.engine_displacement_cc ?? '',
  engine_power_hp: props.editVehicle?.engine_power_hp ?? '',
  body_type: props.editVehicle?.body_type ?? '',
  color: props.editVehicle?.color ?? '',
  plate_chassis: props.editVehicle?.chassis_number ?? '',
  registration_number: props.editVehicle?.registration_number ?? '',
  purchase_price: props.editVehicle?.purchase_price ?? props.editProfile?.purchase_price ?? '',
  initial_industrial_expense: props.editVehicle?.initial_industrial_expense ?? '',
  annual_kasko_cost: props.editVehicle?.annual_kasko_cost ?? '',
  annual_traffic_insurance_cost: props.editVehicle?.annual_traffic_insurance_cost ?? '',
  annual_mtv_cost: props.editVehicle?.annual_mtv_cost ?? '',
  estimated_monthly_maintenance: props.editVehicle?.estimated_monthly_maintenance ?? '',
  annual_inspection_cost: props.editVehicle?.annual_inspection_cost ?? '',
  fuel_tank_capacity_liters: props.editVehicle?.fuel_tank_capacity_liters ?? '',
  purchase_date: props.editProfile?.purchase_date ?? '',
  seller_name: props.editProfile?.seller_name ?? '',
  condition: props.editProfile?.condition ?? 'NEW',
  purchase_km: props.editProfile?.purchase_km ?? 0,
  inspection_result: props.editProfile?.inspection_result ?? '',
  notes: props.editProfile?.notes ?? '',
})

const submitting = ref(false)
const errorMsg = ref('')

const isElectric = computed(() => form.fuel_type === 'ELECTRIC')

function clean(value) {
  if (value === '' || value === null || value === undefined) return undefined
  return value
}

function buildPayload() {
  const vehicleFields = {
    plate_number: form.plate_number.trim(),
    brand: form.brand.trim(),
    model: form.model.trim(),
    production_year: Number(form.production_year),
    package: form.package.trim() || undefined,
    fuel_type: form.fuel_type,
    transmission: form.transmission || undefined,
    body_type: form.body_type || undefined,
    color: form.color.trim(),
    chassis_number: form.plate_chassis.trim(),
    registration_number: form.registration_number.trim(),
    engine_displacement_cc: clean(form.engine_displacement_cc) && Number(form.engine_displacement_cc),
    engine_power_hp: clean(form.engine_power_hp) && Number(form.engine_power_hp),
    purchase_price: clean(form.purchase_price),
    initial_industrial_expense: clean(form.initial_industrial_expense),
    annual_kasko_cost: clean(form.annual_kasko_cost),
    annual_traffic_insurance_cost: clean(form.annual_traffic_insurance_cost),
    annual_mtv_cost: clean(form.annual_mtv_cost),
    estimated_monthly_maintenance: clean(form.estimated_monthly_maintenance),
    annual_inspection_cost: clean(form.annual_inspection_cost),
    fuel_tank_capacity_liters: clean(form.fuel_tank_capacity_liters),
  }

  const profile = {
    purchase_date: form.purchase_date,
    purchase_price: form.purchase_price,
    seller_name: form.seller_name.trim(),
    condition: form.condition,
    purchase_km: Number(form.purchase_km) || 0,
    inspection_result: form.inspection_result.trim(),
    notes: form.notes.trim(),
  }

  const stripUndefined = (obj) =>
    Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined))

  return { ...stripUndefined(vehicleFields), financial_profile: stripUndefined(profile) }
}

async function submit() {
  errorMsg.value = ''
  if (!form.plate_number.trim() || !form.brand.trim() || !form.model.trim()) {
    errorMsg.value = 'Plaka, marka ve model zorunludur.'
    return
  }
  if (!form.purchase_date || !form.purchase_price) {
    errorMsg.value = 'Satın alma tarihi ve alış fiyatı zorunludur.'
    return
  }
  submitting.value = true
  try {
    const payload = buildPayload()
    const saved = isEdit.value
      ? await finance.updateVehicle(props.editVehicle.id, payload)
      : await finance.createVehicle(payload)
    emit('saved', saved)
  } catch (err) {
    const data = err?.response?.data
    if (data && typeof data === 'object') {
      errorMsg.value = Object.entries(data)
        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
        .join(' | ')
    } else {
      errorMsg.value = 'Kayıt sırasında bir hata oluştu.'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <form class="space-y-6" @submit.prevent="submit">
    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-1 text-sm font-semibold text-slate-900">Araç Bilgileri</h3>
      <p class="mb-4 text-xs text-slate-500">Filo künyesi ve teknik özellikler</p>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Plaka *</span>
          <input v-model="form.plate_number" class="rf-input" placeholder="34 ABC 123" :disabled="isEdit" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Marka *</span>
          <input v-model="form.brand" class="rf-input" placeholder="Renault" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Model *</span>
          <input v-model="form.model" class="rf-input" placeholder="Clio" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Paket</span>
          <input v-model="form.package" class="rf-input" placeholder="Touch" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Model Yılı</span>
          <input v-model="form.production_year" type="number" class="rf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Yakıt Tipi</span>
          <select v-model="form.fuel_type" class="rf-input">
            <option v-for="f in FUEL_TYPES" :key="f.value" :value="f.value">{{ f.label }}</option>
          </select>
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Şanzıman</span>
          <select v-model="form.transmission" class="rf-input">
            <option value="">Seçin</option>
            <option v-for="t in TRANSMISSIONS" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Kasa tipi</span>
          <select v-model="form.body_type" class="rf-input">
            <option value="">Seçin</option>
            <option v-for="b in BODY_TYPES" :key="b.value" :value="b.value">{{ b.label }}</option>
          </select>
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Renk</span>
          <input v-model="form.color" class="rf-input" placeholder="Beyaz" />
        </label>
      </div>
      <p class="mt-3 text-xs text-slate-400">
        SIPP kodu ve segment marka, model, yakıt ve şanzımana göre otomatik belirlenir.
        Kilometre takip cihazından güncellenir.
      </p>
    </section>

    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-1 text-sm font-semibold text-slate-800">Satın Alma</h3>
      <p class="mb-4 text-xs text-slate-500">
        Ne zaman ve kaça alındı? Satış kararı sistemde biriken gerçek kâra göre verilir — satış planı sormuyoruz.
      </p>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Satın Alma Tarihi *</span>
          <input v-model="form.purchase_date" type="date" class="rf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Alış Fiyatı (TL) *</span>
          <input v-model="form.purchase_price" type="number" class="rf-input" placeholder="950000" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Sıfır / İkinci El</span>
          <select v-model="form.condition" class="rf-input">
            <option v-for="c in CONDITIONS" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Alış Kilometresi</span>
          <input v-model="form.purchase_km" type="number" class="rf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Satıcı / Galeri</span>
          <input v-model="form.seller_name" class="rf-input" />
        </label>
        <label class="block lg:col-span-2">
          <span class="mb-1 block text-xs font-medium text-slate-500">Ekspertiz Notu</span>
          <input v-model="form.inspection_result" class="rf-input" placeholder="Hasarsız" />
        </label>
      </div>
    </section>

    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-1 text-sm font-semibold text-slate-800">Maliyet Kalemleri</h3>
      <p class="mb-4 text-xs text-slate-500">
        Günlük maliyet, başabaş fiyatı ve “şimdi satayım mı?” kararı bu gerçek giderlerden hesaplanır.
      </p>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block lg:col-span-2">
          <span class="mb-1 block text-xs font-medium text-slate-500">Kiraya Hazırlık Masrafı (TL)</span>
          <input v-model="form.initial_industrial_expense" type="number" class="rf-input" placeholder="Detay, sanayi, ilk depo dolumu…" />
          <span class="mt-0.5 block text-[10px] text-slate-400">Tek seferlik: sanayi, aksesuar ve alışta depo dolumu dahil</span>
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Yıllık Kasko (TL)</span>
          <input v-model="form.annual_kasko_cost" type="number" class="rf-input" placeholder="28000" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Yıllık Trafik Sigortası (TL)</span>
          <input v-model="form.annual_traffic_insurance_cost" type="number" class="rf-input" placeholder="10000" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Yıllık MTV (TL)</span>
          <input v-model="form.annual_mtv_cost" type="number" class="rf-input" placeholder="12000" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Aylık Bakım Bütçesi (TL)</span>
          <input v-model="form.estimated_monthly_maintenance" type="number" class="rf-input" placeholder="2800" />
          <span class="mt-0.5 block text-[10px] text-slate-400">Periyodik bakım, lastik, küçük onarımlar</span>
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Yıllık Muayene / Egzoz (TL)</span>
          <input v-model="form.annual_inspection_cost" type="number" class="rf-input" placeholder="3500" />
        </label>
        <label class="block" :class="{ 'opacity-50': isElectric }">
          <span class="mb-1 block text-xs font-medium text-slate-500">Depo Kapasitesi (litre)</span>
          <input
            v-model="form.fuel_tank_capacity_liters"
            type="number"
            step="0.1"
            class="rf-input"
            placeholder="45"
            :disabled="isElectric"
          />
          <span class="mt-0.5 block text-[10px] text-slate-400">İsteğe bağlı künye bilgisi; maliyete otomatik yansımaz</span>
        </label>
      </div>
    </section>

    <label class="block rounded-xl border border-slate-200 bg-white p-5">
      <span class="mb-1 block text-xs font-medium text-slate-500">Notlar (isteğe bağlı)</span>
      <textarea v-model="form.notes" rows="2" class="rf-input resize-none" placeholder="Ek maliyet veya araç notları…" />
    </label>

    <p v-if="errorMsg" class="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
      {{ errorMsg }}
    </p>

    <div class="flex items-center justify-end gap-3">
      <button type="button" class="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50" @click="emit('cancel')">
        İptal
      </button>
      <button
        type="submit"
        :disabled="submitting"
        class="rf-btn-primary"
      >
        <svg v-if="submitting" class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9" />
        </svg>
        {{ isEdit ? 'Kaydet' : 'Aracı Ekle' }}
      </button>
    </div>
  </form>
</template>

<style scoped>
.rf-input {
  width: 100%;
  border-radius: 0.5rem;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  padding: 0.55rem 0.75rem;
  font-size: 0.875rem;
  color: #334155;
  outline: none;
  transition: border-color 0.15s, background 0.15s, box-shadow 0.15s;
}
.rf-input:focus {
  border-color: #3b82f6;
  background: #fff;
  box-shadow: 0 0 0 3px #dbeafe;
}
.rf-input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
