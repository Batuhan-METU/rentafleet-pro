<script setup>
// Sürücü ekleme sihirbazı — üç adım tek sütunda alt alta gösterilir (sağ
// taraftaki adım şeridi kullanıcı isteğiyle kaldırıldı). scrollToStep,
// zorunlu alan eksikse ilgili adıma yumuşak kaydırmak için hâlâ kullanılıyor.
import { reactive, ref } from 'vue'
import { useDriverStore } from '../../stores/driverStore.js'
import StepDriverIdentity from './StepDriverIdentity.vue'
import StepDriverLicense from './StepDriverLicense.vue'
import StepDriverFinancial from './StepDriverFinancial.vue'

const emit = defineEmits(['saved', 'cancel'])

const store = useDriverStore()

const STEPS = [
  { id: 1, label: 'Kimlik & İletişim', component: StepDriverIdentity },
  { id: 2, label: 'Ehliyet', component: StepDriverLicense },
  { id: 3, label: 'Finans & Risk', component: StepDriverFinancial },
]

const scrollEl = ref(null)

// Tıklanan/hedeflenen adıma tam olarak 300ms'de yumuşak geçişle kaydırır —
// offsetTop yerine ekran koordinatlarından fark hesaplanır (kaydırma alanı
// en yakın "positioned" ata olmayabileceği için offsetTop yanlış konuma
// atlatabilir).
function scrollToStep(id) {
  const container = scrollEl.value
  const target = container?.querySelector(`[data-step-id="${id}"]`)
  if (!container || !target) return
  const startY = container.scrollTop
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
    if (t < 1) requestAnimationFrame(frame)
  }
  requestAnimationFrame(frame)
}

const form = reactive({
  first_name: '',
  last_name: '',
  national_id: '',
  gender: 'MALE',
  birth_date: '',
  phone: '',
  email: '',
  city: '',
  occupation: '',
  monthly_income: '',
  license_number: '',
  license_class: 'B',
  license_issue_date: '',
  license_points: '',
  license_penalty_count: '',
  has_src_certificate: false,
  has_psychotechnical: false,
  findeks_score: '',
  payment_delay_count: '',
  has_enforcement_record: false,
  bank_blacklist_flag: false,
  fraud_suspicion: false,
  document_fraud_suspicion: false,
})

const submitting = ref(false)
const errorMsg = ref('')

function parseApiError(err) {
  const data = err?.response?.data
  if (!data) return 'Sürücü eklenemedi.'
  if (data.error) return data.error
  if (data.detail) return String(data.detail)
  const lines = []
  const walk = (obj, prefix = '') => {
    for (const [key, val] of Object.entries(obj || {})) {
      const label = prefix ? `${prefix}.${key}` : key
      if (Array.isArray(val)) val.forEach((m) => lines.push(`${m}`))
      else if (val && typeof val === 'object') walk(val, label)
      else lines.push(String(val))
    }
  }
  walk(data)
  return lines.join(' · ') || 'Sürücü eklenemedi.'
}

function buildPayload() {
  return {
    driver: {
      first_name: form.first_name.trim(),
      last_name: form.last_name.trim(),
      national_id: form.national_id.trim(),
      gender: form.gender,
      birth_date: form.birth_date,
      phone: form.phone.trim(),
      email: form.email.trim(),
      license_number: form.license_number.trim(),
      license_class: form.license_class.trim() || 'B',
      city: form.city.trim(),
      occupation: form.occupation.trim(),
      monthly_income: form.monthly_income || null,
    },
    // Doğrulama onay kutuları kaldırıldı (kullanıcı talebi) — form zaten
    // müşteriyle yüz yüzeyken personel tarafından dolduruluyor, kimlik ve
    // telefon bu noktada fiilen doğrulanmış sayılır. Aksi halde her yeni
    // sürücü kalıcı olarak "kimlik doğrulanmadı" risk uyarısı alırdı.
    identity: {
      identity_verified: true,
      phone_verified: true,
      document_fraud_suspicion: form.document_fraud_suspicion,
    },
    license: {
      license_issue_date: form.license_issue_date || null,
      license_points: form.license_points === '' ? 0 : Number(form.license_points),
      license_penalty_count: form.license_penalty_count === '' ? 0 : Number(form.license_penalty_count),
      has_src_certificate: form.has_src_certificate,
      has_psychotechnical: form.has_psychotechnical,
    },
    financial: {
      findeks_score: form.findeks_score ? Number(form.findeks_score) : null,
      has_enforcement_record: form.has_enforcement_record,
      bank_blacklist_flag: form.bank_blacklist_flag,
      payment_delay_count: form.payment_delay_count === '' ? 0 : Number(form.payment_delay_count),
      fraud_suspicion: form.fraud_suspicion,
    },
  }
}

async function submit() {
  errorMsg.value = ''
  if (!form.first_name.trim() || !form.last_name.trim() || form.national_id.trim().length !== 11) {
    errorMsg.value = 'Ad, soyad ve 11 haneli TC Kimlik No zorunludur.'
    scrollToStep(1)
    return
  }
  if (!form.birth_date) {
    errorMsg.value = 'Doğum tarihi zorunludur.'
    scrollToStep(1)
    return
  }
  if (!form.phone.trim() || !form.city.trim()) {
    errorMsg.value = 'Telefon ve şehir zorunludur.'
    scrollToStep(1)
    return
  }
  if (!form.license_number.trim() || !form.license_issue_date) {
    errorMsg.value = 'Ehliyet numarası ve ehliyet alım tarihi zorunludur.'
    scrollToStep(2)
    return
  }
  submitting.value = true
  try {
    const driver = await store.createDriver(buildPayload())
    emit('saved', driver)
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
      <!-- Tüm adımlar alt alta, tek kaydırma alanı (sağdaki adım şeridi kaldırıldı) -->
      <div ref="scrollEl" class="min-h-0 flex-1 space-y-8 overflow-y-auto pr-2">
        <section v-for="s in STEPS" :key="s.id" :data-step-id="s.id" class="scroll-mt-1">
          <h3 class="mb-3 flex items-center gap-2 text-base font-bold text-slate-900">
            <span class="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-100 text-xs font-bold text-slate-500">{{ s.id }}</span>
            {{ s.label }}
          </h3>
          <component :is="s.component" :form="form" />
        </section>
      </div>
    </div>

    <div class="flex items-center justify-between gap-3 border-t border-slate-100 pt-4">
      <button type="button" class="rf-btn-secondary" @click="emit('cancel')">İptal</button>
      <button type="button" class="rf-btn-primary" :disabled="submitting" @click="submit">
        {{ submitting ? 'Kaydediliyor…' : 'Sürücüyü Ekle' }}
      </button>
    </div>
  </div>
</template>
