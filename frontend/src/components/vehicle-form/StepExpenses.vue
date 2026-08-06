<script setup>
import { computed, onMounted, ref } from 'vue'
import { useFinanceStore } from '../../stores/financeStore.js'
import { formatDate, formatTL, formatNumber } from '../../utils/format.js'
import DatePicker from './DatePicker.vue'
import SearchableSelect from './SearchableSelect.vue'

const props = defineProps({
  form: { type: Object, required: true },
  policies: { type: Object, required: true },
})

const finance = useFinanceStore()
const expenseCategoryOptions = ref([])
const existingExpenses = ref([])
onMounted(async () => {
  try {
    const categories = await finance.fetchExpenseCategories()
    expenseCategoryOptions.value = categories.map((c) => ({ value: c.value, label: c.label }))
    // Düzenleme modunda, bu araca daha önce girilmiş operasyon giderlerini
    // göster — aksi halde kullanıcı az önce ekleyip kaydettiği bir gideri
    // sihirbazı tekrar açtığında hiç göremiyor, sanki kaydedilmemiş gibi
    // görünüyordu.
    if (props.form.id) {
      existingExpenses.value = await finance.fetchExpenses(props.form.id)
    }
  } catch (err) {
    console.error('Gider kategorileri/mevcut giderler yüklenemedi:', err)
  }
})

const FINANCING_TYPES = [
  { value: 'CASH', label: 'Nakit' },
  { value: 'LOAN', label: 'Kredi' },
  { value: 'MIXED', label: 'Karma' },
]
const POLICY_TYPES = [
  { value: 'LIABILITY', label: 'Trafik Sigortası' },
  { value: 'COMPREHENSIVE', label: 'Kasko' },
  { value: 'GREEN_CARD', label: 'Yeşil Kart' },
]

const isLoanOnly = computed(() => props.form.financing_type === 'LOAN')

function addExpenseRow() {
  props.form.operatingExpenses.push({
    category: '',
    custom_label: '',
    amount: '',
    expense_date: '',
    odometer_km: '',
    income_amount: '',
    income_source: '',
    _incomeOpen: false,
  })
}
function removeExpenseRow(idx) {
  props.form.operatingExpenses.splice(idx, 1)
}

// "Araç Bakım" seçilince, henüz km girilmediyse aracın bilinen güncel
// km'si otomatik önerilir (Bakım Merkezi'nin "son bakım km"si buradan
// beslenir) — kullanıcı isterse değiştirir, bir daha zorla üzerine
// yazılmaz.
function onCategoryChange(row, category) {
  row.category = category
  if (category === 'VEHICLE_MAINTENANCE' && !row.odometer_km) {
    row.odometer_km = props.form.current_km || ''
  }
}
</script>

<template>
  <div class="space-y-5">
    <!-- Operasyon -->
    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <div class="mb-1 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-slate-800">Operasyon</h3>
        <button type="button" class="rf-btn-secondary !px-3 !py-1.5 text-xs" @click="addExpenseRow">
          + Gider Satırı Ekle
        </button>
      </div>
      <p class="mb-4 text-xs text-slate-500">
        Bakım, lastik, hasar, yakıt gibi araca özel gider kayıtları — Araç
        Detayı'ndaki "Operasyon" maliyetini doğrudan bu kayıtlar besler.
      </p>

      <!-- Mevcut kayıtlar (düzenleme modu) -->
      <div v-if="form.id && existingExpenses.length" class="mb-4">
        <p class="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
          Daha Önce Girilmiş Kayıtlar ({{ existingExpenses.length }})
        </p>
        <ul class="max-h-40 divide-y divide-slate-100 overflow-y-auto rounded-lg border border-slate-100">
          <li v-for="exp in existingExpenses" :key="exp.id" class="flex items-center gap-3 px-3 py-2 text-xs">
            <span class="min-w-0 flex-1 truncate font-medium text-slate-700">{{ exp.label }}</span>
            <span class="shrink-0 text-slate-400">{{ formatDate(exp.expense_date) }}</span>
            <span v-if="exp.odometer_km != null" class="shrink-0 text-slate-400">{{ formatNumber(exp.odometer_km) }} km</span>
            <span class="shrink-0 font-mono font-semibold text-slate-800">{{ formatTL(exp.amount, { decimals: true }) }}</span>
          </li>
        </ul>
      </div>

      <div v-if="!form.operatingExpenses.length" class="rounded-lg border border-dashed border-slate-200 py-6 text-center text-xs text-slate-400">
        Henüz yeni gider satırı eklenmedi.
      </div>
      <div v-for="(row, idx) in form.operatingExpenses" :key="idx" class="mb-3 rounded-lg border border-slate-100 bg-slate-50/60 p-3">
        <div class="grid grid-cols-2 gap-3 md:grid-cols-6">
          <label class="block md:col-span-2">
            <span class="mb-1 block text-[10px] font-medium text-slate-500">Kategori <span class="text-rose-500">*</span></span>
            <SearchableSelect :model-value="row.category" :options="expenseCategoryOptions" @update:model-value="(v) => onCategoryChange(row, v)" />
          </label>
          <label class="block">
            <span class="mb-1 block text-[10px] font-medium text-slate-500">Tutar (TL) <span class="text-rose-500">*</span></span>
            <input v-model="row.amount" type="number" step="0.01" class="vf-input" />
          </label>
          <label class="block">
            <span class="mb-1 block text-[10px] font-medium text-slate-500">Tarih <span class="text-rose-500">*</span></span>
            <DatePicker v-model="row.expense_date" />
          </label>
          <label class="block">
            <span class="mb-1 block text-[10px] font-medium text-slate-500">
              Kilometre
              <span v-if="row.category === 'VEHICLE_MAINTENANCE'" class="text-rose-500">*</span>
              <span v-else class="text-slate-400">(ops.)</span>
            </span>
            <input v-model="row.odometer_km" type="number" min="0" class="vf-input" />
          </label>
          <div class="flex items-end gap-2">
            <label class="block flex-1">
              <span class="mb-1 block text-[10px] font-medium text-slate-500">Açıklama (ops.)</span>
              <input v-model="row.custom_label" class="vf-input" />
            </label>
            <button type="button" class="mb-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg text-slate-400 hover:bg-rose-50 hover:text-rose-600" @click="removeExpenseRow(idx)">
              ✕
            </button>
          </div>
        </div>

        <!-- Gelir (ops.) — bu gidere bağlı bir geri kazanım/tahsilat varsa
             (ör. sigorta tazminatı). Varsayılan kapalı, çoğu giderde yok. -->
        <button
          v-if="!row._incomeOpen && !row.income_amount"
          type="button"
          class="mt-2 text-[11px] font-semibold text-brand-600 hover:text-brand-700"
          @click="row._incomeOpen = true"
        >
          + Gelir Ekle (sigorta tazminatı, tahsilat vb.)
        </button>
        <div v-else class="mt-2 grid grid-cols-2 gap-3 border-t border-slate-200 pt-2 md:grid-cols-6">
          <label class="block">
            <span class="mb-1 block text-[10px] font-medium text-slate-500">Gelir (TL)</span>
            <input v-model="row.income_amount" type="number" step="0.01" class="vf-input" />
          </label>
          <label class="block md:col-span-2">
            <span class="mb-1 block text-[10px] font-medium text-slate-500">Gelir Kaynağı</span>
            <input v-model="row.income_source" placeholder="Sigorta tazminatı, müşteri tahsilatı..." class="vf-input" />
          </label>
          <button
            type="button"
            class="mb-0.5 h-fit self-end text-[11px] font-semibold text-slate-400 hover:text-rose-600"
            @click="row._incomeOpen = false; row.income_amount = ''; row.income_source = ''"
          >
            Geliri kaldır
          </button>
        </div>
      </div>
    </section>

    <!-- Finansman -->
    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-1 text-sm font-semibold text-slate-800">Finansman</h3>
      <p class="mb-4 text-xs text-slate-500">
        Gerçek maliyet hesabının kredi faizi / nakit fırsat maliyeti ayrımı
        buradan başlar. Kredi bağlantısını (hangi kredi ne kadar finanse
        ediyor) <strong>Krediler</strong> sayfasından yapabilirsiniz.
      </p>
      <div class="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-4">
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Filoya Giriş Tarihi</span>
          <DatePicker v-model="form.fleet_entry_date" />
          <span class="mt-0.5 block text-[10px] text-slate-400">Maliyet hesabının zaman ekseni buradan başlar</span>
        </label>
        <label class="block">
          <span class="mb-1 block text-xs font-medium text-slate-500">Finansman Tipi</span>
          <select v-model="form.financing_type" class="vf-input">
            <option v-for="f in FINANCING_TYPES" :key="f.value" :value="f.value">{{ f.label }}</option>
          </select>
        </label>
        <label class="block" :class="{ 'opacity-50': isLoanOnly }">
          <span class="mb-1 block text-xs font-medium text-slate-500">Nakit Finanse Edilen Tutar (TL)</span>
          <input
            v-model="form.cash_financed_amount"
            type="number"
            step="0.01"
            class="vf-input"
            :disabled="isLoanOnly"
          />
          <span class="mt-0.5 block text-[10px] text-slate-400">
            Karma'da aracın kredi dışı kalan kısmı; Kredi'de boş bırakılır
          </span>
        </label>
      </div>
    </section>

    <!-- Sigorta/Kasko -->
    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <h3 class="mb-1 text-sm font-semibold text-slate-800">Sigorta/Kasko</h3>
      <p class="mb-4 text-xs text-slate-500">
        Aracın güncel poliçeleri — "Poliçeler" sekmesinde görünecek ve gerçek
        maliyet hesabına (sigorta bileşeni) doğrudan girer. Boş bırakılan tip
        kaydedilmez.
      </p>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div v-for="pt in POLICY_TYPES" :key="pt.value" class="rounded-lg border border-slate-100 bg-slate-50/60 p-3">
          <p class="mb-2 text-xs font-semibold text-slate-700">{{ pt.label }}</p>
          <label class="mb-2 block">
            <span class="mb-1 block text-[10px] font-medium text-slate-500">Tutar (TL)</span>
            <input v-model="policies[pt.value].amount" type="number" step="0.01" class="vf-input" />
          </label>
          <div class="grid grid-cols-2 gap-2">
            <label class="block">
              <span class="mb-1 block text-[10px] font-medium text-slate-500">Başlangıç</span>
              <DatePicker v-model="policies[pt.value].start_date" />
            </label>
            <label class="block">
              <span class="mb-1 block text-[10px] font-medium text-slate-500">Bitiş</span>
              <DatePicker v-model="policies[pt.value].end_date" />
            </label>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
