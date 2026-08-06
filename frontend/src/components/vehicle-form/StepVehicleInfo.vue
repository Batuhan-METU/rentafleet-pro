<script setup>
import SearchableSelect from './SearchableSelect.vue'

defineProps({
  form: { type: Object, required: true },
  isEdit: { type: Boolean, default: false },
})

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
</script>

<template>
  <div class="space-y-5">
    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-1 text-sm font-semibold text-slate-900">Araç Künyesi</h3>
      <p class="mb-4 text-xs text-slate-500">
        Plaka, marka ve model zorunludur — Ruhsat Bilgileri adımında da aynı
        alanlar (resmi belge etiketleriyle) yeniden görünür.
      </p>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Plaka *</span>
          <input v-model="form.plate_number" class="vf-input" :disabled="isEdit" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Marka *</span>
          <input v-model="form.brand" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Model *</span>
          <input v-model="form.model" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Model Yılı</span>
          <input v-model="form.production_year" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Yakıt Tipi</span>
          <SearchableSelect v-model="form.fuel_type" :options="FUEL_TYPES" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Renk</span>
          <input v-model="form.color" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Silindir Hacmi (cm³)</span>
          <input v-model="form.engine_displacement_cc" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Motor Gücü (hp)</span>
          <input v-model="form.engine_power_hp" type="number" class="vf-input" />
        </label>
      </div>
    </section>

    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-1 text-sm font-semibold text-slate-900">Araç Bilgileri</h3>
      <p class="mb-4 text-xs text-slate-500">Kasa tipi, kilometre ve donanım detayları.</p>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Kasa Tipi</span>
          <SearchableSelect v-model="form.body_type" :options="BODY_TYPES" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Kilometre (km)</span>
          <input v-model="form.current_km" type="number" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Yakıt Kapasitesi (Lt)</span>
          <input v-model="form.fuel_tank_capacity_liters" type="number" step="0.1" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Araç Paketi</span>
          <input v-model="form.package" class="vf-input" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Vites</span>
          <SearchableSelect v-model="form.transmission" :options="TRANSMISSIONS" />
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Giydirme</span>
          <input v-model="form.registration.dressing_info" class="vf-input" />
        </label>
        <label class="block lg:col-span-2">
          <span class="mb-1 block text-xs font-medium text-slate-500">Ekstra Donanım Bilgisi</span>
          <input v-model="form.registration.extra_equipment_notes" class="vf-input" />
        </label>
      </div>
    </section>
  </div>
</template>
