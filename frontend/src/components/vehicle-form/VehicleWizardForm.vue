<script setup>
// FYS ruhsat-tipi araç ekleme sihirbazı — 10 adım (FYS'nin 9 adımı +
// bizim sistemimizin zorunlu girdisi olan "Giderler": Operasyon/
// Finansman/Sigorta — Araç Detayı'ndaki maliyet kırılımıyla birebir).
// "Şasi Sorgulama" kaldırıldı (çalışan bir VIN kaynağı yok, kullanıcıyla
// netleştirildi) — düz "Şasi Numarası" metin kutusu. "Dosyalar ve Ekler"
// adımı "Yakında" (dosya depolama altyapısı bu işin kapsamı dışında).
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useFinanceStore } from '../../stores/financeStore.js'
import StepCatalog from './StepCatalog.vue'
import StepGeneral from './StepGeneral.vue'
import StepVehicleInfo from './StepVehicleInfo.vue'
import StepInvoice from './StepInvoice.vue'
import StepInspection from './StepInspection.vue'
import StepRegistration from './StepRegistration.vue'
import StepExpenses from './StepExpenses.vue'
import StepFiles from './StepFiles.vue'

const props = defineProps({
  editVehicle: { type: Object, default: null },
  editProfile: { type: Object, default: null },
  editPolicies: { type: Array, default: () => [] },
  editRegistrationDetail: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'cancel'])

const finance = useFinanceStore()
const isEdit = computed(() => !!props.editVehicle)

const STEPS = [
  { id: 1, label: 'Katalog Bilgileri', component: StepCatalog, ready: true },
  { id: 2, label: 'Genel Bilgiler', component: StepGeneral, ready: true },
  { id: 3, label: 'Araç Bilgileri', component: StepVehicleInfo, ready: true },
  { id: 4, label: 'Fatura Bilgileri', component: StepInvoice, ready: true },
  { id: 5, label: 'Muayene/TÜV Bilgileri', component: StepInspection, ready: true },
  { id: 6, label: 'Ruhsat Bilgileri', component: StepRegistration, ready: true },
  { id: 7, label: 'Giderler', component: StepExpenses, ready: true },
  { id: 8, label: 'Dosyalar ve Ekler', component: StepFiles, ready: true },
]

// --- Sağdaki adım şeridi + kaydırma ile senkron aktif adım (scroll-spy) --
const scrollEl = ref(null)
const activeStep = ref(1)
let observer = null
let suppressSpy = false

function setupObserver() {
  if (!scrollEl.value) return
  observer = new IntersectionObserver(
    (entries) => {
      if (suppressSpy) return
      const visible = entries.filter((e) => e.isIntersecting)
      if (!visible.length) return
      visible.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)
      activeStep.value = Number(visible[0].target.dataset.stepId)
    },
    { root: scrollEl.value, rootMargin: '0px 0px -55% 0px', threshold: 0 },
  )
  scrollEl.value.querySelectorAll('[data-step-id]').forEach((el) => observer.observe(el))
}

onMounted(() => nextTick(setupObserver))
onBeforeUnmount(() => observer?.disconnect())

// Tıklanan adıma tam olarak 300ms'de (kullanıcının istediği "0.3 saniye")
// yumuşak geçişle kaydırır — tarayıcının kendi "smooth" davranışının süresi
// standart olmadığı için elle, hassas bir animasyon kullanılır.
function scrollToStep(id) {
  const container = scrollEl.value
  const target = container?.querySelector(`[data-step-id="${id}"]`)
  if (!container || !target) return
  activeStep.value = id
  suppressSpy = true
  const startY = container.scrollTop
  // offsetTop, en yakın "positioned" ataya göredir — bu her zaman kaydırma
  // alanının kendisi olmayabileceği için (yanlış konuma atlama hatası),
  // bunun yerine ekran koordinatlarından SAĞLAM bir fark hesaplanır.
  const targetRect = target.getBoundingClientRect()
  const containerRect = container.getBoundingClientRect()
  const endY = startY + (targetRect.top - containerRect.top)
  const distance = endY - startY
  const duration = 300
  const startTime = performance.now()
  function frame(now) {
    const t = Math.min((now - startTime) / duration, 1)
    const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
    container.scrollTop = startY + distance * eased
    if (t < 1) {
      requestAnimationFrame(frame)
    } else {
      suppressSpy = false
    }
  }
  requestAnimationFrame(frame)
}

const rd = props.editRegistrationDetail

const POLICY_TYPES = ['LIABILITY', 'COMPREHENSIVE', 'GREEN_CARD']
function initialPolicyState(type) {
  const existing = props.editPolicies.find((p) => p.policy_type === type)
  return {
    amount: existing?.amount ?? '',
    start_date: existing?.start_date ?? '',
    end_date: existing?.end_date ?? '',
  }
}
const policies = reactive(Object.fromEntries(POLICY_TYPES.map((t) => [t, initialPolicyState(t)])))

const form = reactive({
  // --- Araç künyesi (Araç Bilgileri / Ruhsat'ta tekrar gösterilir) -----
  id: props.editVehicle?.id ?? null,
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
  sipp_code: props.editVehicle?.sipp_code ?? '',
  branch_name: props.editVehicle?.branch_name ?? '',
  current_km: props.editVehicle?.current_km ?? 0,
  fuel_tank_capacity_liters: props.editVehicle?.fuel_tank_capacity_liters ?? '',
  purchase_invoice_date: props.editVehicle?.purchase_invoice_date ?? '',
  fleet_entry_date: props.editVehicle?.fleet_entry_date ?? '',

  // --- Giderler adımı (Operasyon/Finansman/Sigorta) ----------------------
  purchase_price: props.editVehicle?.purchase_price ?? props.editProfile?.purchase_price ?? '',
  purchase_date: props.editProfile?.purchase_date ?? '',
  seller_name: props.editProfile?.seller_name ?? '',
  condition: props.editProfile?.condition ?? 'NEW',
  purchase_km: props.editProfile?.purchase_km ?? 0,
  inspection_result: props.editProfile?.inspection_result ?? '',
  notes: props.editProfile?.notes ?? '',
  financing_type: props.editProfile?.financing_type ?? 'CASH',
  cash_financed_amount: props.editProfile?.cash_financed_amount ?? '',
  operatingExpenses: [],
  stagedFiles: [],

  // --- registration_detail (FYS'e özgü ek alanlar) ----------------------
  registration: {
    catalog_production_year_start: rd?.catalog_production_year_start ?? '',
    catalog_production_year_end: rd?.catalog_production_year_end ?? '',
    list_price: rd?.list_price ?? '',
    tafim_price: rd?.tafim_price ?? '',
    dressing_info: rd?.dressing_info ?? '',
    extra_equipment_notes: rd?.extra_equipment_notes ?? '',
    invoice_number: rd?.invoice_number ?? '',
    invoice_amount: rd?.invoice_amount ?? '',
    inspection_valid_until: rd?.inspection_valid_until ?? '',
    registration_serial_no: rd?.registration_serial_no ?? '',
    registration_province: rd?.registration_province ?? '',
    registration_district: rd?.registration_district ?? '',
    first_registration_date: rd?.first_registration_date ?? '',
    registration_sequence_no: rd?.registration_sequence_no ?? '',
    registration_date: rd?.registration_date ?? '',
    vehicle_type_code: rd?.vehicle_type_code ?? '',
    vehicle_class: rd?.vehicle_class ?? '',
    vehicle_kind: rd?.vehicle_kind ?? '',
    engine_serial_number: rd?.engine_serial_number ?? '',
    net_weight_kg: rd?.net_weight_kg ?? '',
    max_loaded_weight_kg: rd?.max_loaded_weight_kg ?? '',
    train_weight_kg: rd?.train_weight_kg ?? '',
    trailer_max_weight_kg: rd?.trailer_max_weight_kg ?? '',
    seat_count: rd?.seat_count ?? '',
    standing_passenger_count: rd?.standing_passenger_count ?? '',
    power_to_weight_ratio: rd?.power_to_weight_ratio ?? '',
    usage_purpose: rd?.usage_purpose ?? '',
    type_approval_no: rd?.type_approval_no ?? '',
    owner_tc_or_tax_no: rd?.owner_tc_or_tax_no ?? '',
    owner_surname_or_title: rd?.owner_surname_or_title ?? '',
    owner_first_name: rd?.owner_first_name ?? '',
    owner_address: rd?.owner_address ?? '',
    rights_holders_note: rd?.rights_holders_note ?? '',
    other_notes: rd?.other_notes ?? '',
  },
})

const submitting = ref(false)
const errorMsg = ref('')

const isLoanOnly = computed(() => form.financing_type === 'LOAN')

watch(
  () => form.financing_type,
  (type) => {
    if (type === 'CASH' && !form.cash_financed_amount) {
      form.cash_financed_amount = form.purchase_price
    }
    if (type === 'LOAN') {
      form.cash_financed_amount = ''
    }
  },
)

function clean(value) {
  if (value === '' || value === null || value === undefined) return undefined
  return value
}
const stripUndefined = (obj) => Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== undefined))

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
    sipp_code: form.sipp_code.trim() || undefined,
    branch_name: form.branch_name.trim(),
    engine_displacement_cc: clean(form.engine_displacement_cc) && Number(form.engine_displacement_cc),
    engine_power_hp: clean(form.engine_power_hp) && Number(form.engine_power_hp),
    purchase_price: clean(form.purchase_price),
    fuel_tank_capacity_liters: clean(form.fuel_tank_capacity_liters),
    purchase_invoice_date: clean(form.purchase_invoice_date),
    fleet_entry_date: clean(form.fleet_entry_date),
  }

  const profile = {
    purchase_date: form.purchase_date,
    purchase_price: form.purchase_price,
    seller_name: form.seller_name.trim(),
    condition: form.condition,
    purchase_km: Number(form.purchase_km) || 0,
    inspection_result: form.inspection_result.trim(),
    notes: form.notes.trim(),
    financing_type: form.financing_type,
    cash_financed_amount: isLoanOnly.value ? undefined : clean(form.cash_financed_amount),
  }

  const insurance_policies = Object.entries(policies)
    .filter(([, p]) => p.amount && p.start_date && p.end_date)
    .map(([policy_type, p]) => ({
      policy_type,
      amount: p.amount,
      start_date: p.start_date,
      end_date: p.end_date,
    }))

  const registrationFields = stripUndefined(
    Object.fromEntries(Object.entries(form.registration).map(([k, v]) => [k, clean(v)])),
  )

  const operating_expenses = form.operatingExpenses
    .filter((row) => row.category && row.amount && row.expense_date)
    .map((row) => ({
      category: row.category,
      custom_label: row.custom_label?.trim() || '',
      amount: row.amount,
      expense_date: row.expense_date,
      odometer_km: row.odometer_km === '' || row.odometer_km == null ? undefined : Number(row.odometer_km),
      income_amount: row.income_amount === '' || row.income_amount == null ? undefined : Number(row.income_amount),
      income_source: row.income_source?.trim() || undefined,
    }))

  return {
    ...stripUndefined(vehicleFields),
    financial_profile: stripUndefined(profile),
    insurance_policies,
    registration_detail: registrationFields,
    operating_expenses,
  }
}

function parseApiError(err) {
  const data = err?.response?.data
  if (!data || typeof data !== 'object') return 'Kayıt sırasında bir hata oluştu.'
  return Object.entries(data)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
    .join(' | ')
}

// Bir Operasyon satırına "başlanmış" sayılır sayılmaz (herhangi bir alanı
// doldurulmuşsa) zorunlu alanları tamamlanmadan kaydetmeye izin verilmez —
// aksi halde satır sessizce (hatasız) atlanır ve kullanıcı aracın
// kaydedildiğini ama giderin hiç eklenmediğini fark etmez.
function findIncompleteExpenseRowError() {
  for (const row of form.operatingExpenses) {
    const touched =
      row.category || row.amount || row.expense_date || row.custom_label || row.odometer_km ||
      row.income_amount || row.income_source
    if (!touched) continue
    if (!row.category || !row.amount || !row.expense_date) {
      return 'Giderler adımındaki bir Operasyon satırında kategori, tutar ve tarih zorunludur.'
    }
    if (row.category === 'VEHICLE_MAINTENANCE' && !row.odometer_km) {
      return 'Giderler adımında "Araç Bakım" kategorisi için kilometre girilmesi zorunludur.'
    }
  }
  return null
}

async function submit() {
  errorMsg.value = ''
  if (!form.plate_number.trim() || !form.brand.trim() || !form.model.trim()) {
    errorMsg.value = 'Plaka, marka ve model zorunludur (Araç Bilgileri ya da Ruhsat Bilgileri adımından girin).'
    scrollToStep(3)
    return
  }
  if (!form.purchase_date || !form.purchase_price) {
    errorMsg.value = 'Satın alma tarihi ve alış fiyatı zorunludur (Genel Bilgiler adımından girin).'
    scrollToStep(2)
    return
  }
  const expenseError = findIncompleteExpenseRowError()
  if (expenseError) {
    errorMsg.value = expenseError
    scrollToStep(7)
    return
  }
  submitting.value = true
  try {
    const payload = buildPayload()
    const saved = isEdit.value
      ? await finance.updateVehicle(props.editVehicle.id, payload)
      : await finance.createVehicle(payload)
    // Yeni araçta dosyalar "Dosyalar ve Ekler" adımında araç ID'si olmadığı
    // için beklemede tutulmuştu (form.stagedFiles) — araç kaydı başarılı
    // olur olmaz burada gerçek yükleme yapılır. Düzenleme modunda dosyalar
    // zaten anında yükleniyor (StepFiles.vue), staged liste kullanılmaz.
    if (!isEdit.value && form.stagedFiles.length) {
      const results = await Promise.allSettled(
        form.stagedFiles.map((item) => finance.uploadDocument(saved.id, item.file, item.label)),
      )
      if (results.some((r) => r.status === 'rejected')) {
        errorMsg.value = 'Araç kaydedildi ama bazı dosyalar yüklenemedi — Dosyalar sekmesinden tekrar deneyin.'
      }
    }
    emit('saved', saved)
  } catch (err) {
    errorMsg.value = parseApiError(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col gap-4">
    <p v-if="errorMsg" class="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
      {{ errorMsg }}
    </p>

    <div class="flex min-h-0 flex-1 gap-6">
      <!-- Sol: tüm adımlar alt alta, tek kaydırma alanı -->
      <div ref="scrollEl" class="min-h-0 flex-1 space-y-8 overflow-y-auto pr-2">
        <section v-for="s in STEPS" :key="s.id" :data-step-id="s.id" class="scroll-mt-1">
          <h3 class="mb-3 flex items-center gap-2 text-base font-bold text-slate-900">
            <span class="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-bold text-slate-500">{{ s.id }}</span>
            {{ s.label }}
          </h3>
          <component :is="s.component" :form="form" :policies="policies" :is-edit="isEdit" />
        </section>
      </div>

      <!-- Sağ: sabit (sticky) adım şeridi, aşağı kaydırdıkça aktif adım değişir -->
      <nav class="hidden w-56 shrink-0 md:block">
        <ul class="sticky top-0 space-y-1">
          <li v-for="s in STEPS" :key="s.id">
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold transition-colors"
              :class="activeStep === s.id ? 'bg-brand-50 text-brand-700' : 'text-slate-500 hover:bg-slate-50'"
              @click="scrollToStep(s.id)"
            >
              <span
                class="grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-bold"
                :class="activeStep === s.id ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'"
              >{{ s.id }}</span>
              <span class="min-w-0 flex-1 truncate">{{ s.label }}</span>
              <span v-if="!s.ready" class="shrink-0 text-[9px] font-bold uppercase text-slate-300">Yakında</span>
            </button>
          </li>
        </ul>
      </nav>
    </div>

    <div class="flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
      <button type="button" class="rf-btn-secondary" @click="emit('cancel')">İptal</button>
      <button type="button" class="rf-btn-primary" :disabled="submitting" @click="submit">
        {{ submitting ? 'Kaydediliyor…' : isEdit ? 'Kaydet' : 'Aracı Ekle' }}
      </button>
    </div>
  </div>
</template>
