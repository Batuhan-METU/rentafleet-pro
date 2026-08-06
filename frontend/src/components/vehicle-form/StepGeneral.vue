<script setup>
import SearchableSelect from './SearchableSelect.vue'
import DatePicker from './DatePicker.vue'

defineProps({
  form: { type: Object, required: true },
})

// Filoda gerçekten kullanılan SIPP/ACRISS kodları (uydurma bir referans
// listesi değil — mevcut araçlardan derlendi).
const SIPP_CODES = [
  'CDAD', 'CDMD', 'CDMR', 'CFAD', 'CFAH', 'CFAR', 'DFAR', 'EDAD', 'EDAR',
  'EDMD', 'EDMR', 'EWMD', 'EXAD', 'FFAH', 'FXAR', 'IDAD', 'IDAH', 'IDAR',
  'IDMR', 'IFMR', 'IWAD', 'IXAR', 'LVAD', 'LVAR', 'PDAR', 'SDAR', 'SFAD',
  'SFAE', 'SFAR', 'XQBD',
].map((code) => ({ value: code, label: code }))
</script>

<template>
  <section class="rounded-xl border border-slate-200 bg-white p-5">
    <h3 class="mb-1 text-sm font-semibold text-slate-900">Genel Bilgiler</h3>
    <p class="mb-4 text-xs text-slate-500">Ofis, satın alma ve katalog fiyat bilgileri.</p>
    <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Ofis</span>
        <input v-model="form.branch_name" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Araç Grubu</span>
        <SearchableSelect v-model="form.sipp_code" :options="SIPP_CODES" />
        <span class="mt-0.5 block text-[10px] text-slate-400">Boş bırakılırsa marka/modelden otomatik belirlenir</span>
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Satın Alma Tarihi *</span>
        <DatePicker v-model="form.purchase_date" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Satın Alma Fiyatı (TL) *</span>
        <input v-model="form.purchase_price" type="number" step="0.01" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Başlangıç Üretim Yılı</span>
        <input v-model="form.registration.catalog_production_year_start" type="number" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Bitiş Üretim Yılı</span>
        <input v-model="form.registration.catalog_production_year_end" type="number" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Liste Fiyatı (TL)</span>
        <input v-model="form.registration.list_price" type="number" step="0.01" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Tafim Fiyatı (TL)</span>
        <input v-model="form.registration.tafim_price" type="number" step="0.01" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Alış Kilometresi</span>
        <input v-model="form.purchase_km" type="number" class="vf-input" />
      </label>
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-500">Satıcı / Galeri</span>
        <input v-model="form.seller_name" class="vf-input" />
      </label>
      <label class="block lg:col-span-2">
        <span class="mb-1 block text-xs font-medium text-slate-500">Ekspertiz Notu</span>
        <input v-model="form.inspection_result" class="vf-input" />
      </label>
    </div>
    <label class="mt-4 block">
      <span class="mb-1 block text-xs font-medium text-slate-500">Notlar (isteğe bağlı)</span>
      <textarea v-model="form.notes" rows="2" class="vf-input resize-none" />
    </label>
  </section>
</template>
