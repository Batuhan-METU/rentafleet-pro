<script setup>
import { computed, reactive, ref } from 'vue'
import { useDriverStore } from '../stores/driverStore.js'
import { useRentalWorkflowStore } from '../stores/rentalWorkflowStore.js'

const emit = defineEmits(['close', 'saved'])

const store = useDriverStore()
const workflow = useRentalWorkflowStore()
const step = ref(1)
const loading = ref(false)
const error = ref('')

const form = reactive({
  driver: {
    first_name: '',
    last_name: '',
    national_id: '',
    gender: 'MALE',
    birth_date: '',
    phone: '',
    email: '',
    license_number: '',
    license_class: 'B',
    city: '',
    district: '',
    address: '',
    occupation: '',
    employer: '',
    monthly_income: '',
  },
  identity: {
    identity_verified: false,
    phone_verified: false,
    email_verified: false,
    document_fraud_suspicion: false,
  },
  license: {
    license_issue_date: '',
    license_points: 0,
    license_penalty_count: 0,
    has_src_certificate: false,
    has_psychotechnical: false,
  },
  financial: {
    findeks_score: '',
    has_enforcement_record: false,
    bank_blacklist_flag: false,
    payment_delay_count: 0,
    fraud_suspicion: false,
  },
})

const steps = [
  { id: 1, label: 'Kimlik & İletişim' },
  { id: 2, label: 'Ehliyet' },
  { id: 3, label: 'Finans' },
]

const canGoNext = computed(() => {
  if (step.value === 1) {
    const d = form.driver
    return d.first_name.trim() && d.last_name.trim() && d.national_id.trim().length === 11
      && d.birth_date && d.phone.trim() && d.city.trim()
  }
  if (step.value === 2) {
    return form.driver.license_number.trim() && form.license.license_issue_date
  }
  return true
})

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
      ...form.driver,
      email: form.driver.email.trim() || '',
      monthly_income: form.driver.monthly_income || null,
    },
    identity: { ...form.identity },
    license: {
      ...form.license,
      license_issue_date: form.license.license_issue_date || null,
    },
    financial: {
      ...form.financial,
      findeks_score: form.financial.findeks_score ? Number(form.financial.findeks_score) : null,
    },
  }
}

async function submit() {
  loading.value = true
  error.value = ''
  try {
    const driver = await store.createDriver(buildPayload())
    emit('saved', driver)
  } catch (e) {
    error.value = parseApiError(e)
  } finally {
    loading.value = false
  }
}

function onKeydown(event) {
  if (event.key === 'Escape') emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 sm:p-6" @click.self="emit('close')">
      <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" />
      <div class="relative my-4 w-full max-w-3xl overflow-hidden rounded-3xl rf-glass-strong shadow-2xl">
        <div class="rf-accent-bar" />
        <header class="flex items-center justify-between border-b border-white/30 px-6 py-4">
          <div>
            <h2 class="text-lg font-bold text-slate-900">Yeni Sürücü Ekle</h2>
            <p class="text-sm text-slate-500">Kayıt sonrası risk skoru ve uygun araçlar otomatik hesaplanır.</p>
          </div>
          <button type="button" class="grid h-9 w-9 place-items-center rounded-lg text-slate-400 hover:bg-slate-100" @click="emit('close')">✕</button>
        </header>

        <div class="px-6 py-5">
          <div class="mb-5 flex flex-wrap gap-2">
            <span
              v-for="s in steps"
              :key="s.id"
              class="rounded-full px-3 py-1 text-xs font-bold"
              :class="step === s.id ? 'bg-brand-600 text-white' : 'bg-white/60 text-slate-500'"
            >
              {{ s.id }}. {{ s.label }}
            </span>
          </div>

          <div v-if="workflow.active" class="mb-4 rounded-2xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-800">
            <strong>Adım 2 — Sürücü bilgileri.</strong> Müşteri fiyatı kabul etti; bilgilerini girin.
            <span v-if="workflow.vehicleLabel" class="mt-1 block text-xs">Araç: {{ workflow.vehicleLabel }}</span>
          </div>

          <div v-if="error" class="mb-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {{ error }}
          </div>

          <div v-if="step === 1" class="grid gap-4 md:grid-cols-2">
            <input v-model="form.driver.first_name" class="rf-input" placeholder="Ad *" required />
            <input v-model="form.driver.last_name" class="rf-input" placeholder="Soyad *" required />
            <input v-model="form.driver.national_id" class="rf-input" placeholder="TC Kimlik No *" maxlength="11" required />
            <input v-model="form.driver.birth_date" type="date" class="rf-input" required />
            <select v-model="form.driver.gender" class="rf-input">
              <option value="MALE">Erkek</option>
              <option value="FEMALE">Kadın</option>
              <option value="OTHER">Diğer</option>
            </select>
            <input v-model="form.driver.phone" class="rf-input" placeholder="Telefon *" required />
            <input v-model="form.driver.email" type="email" class="rf-input" placeholder="E-posta" />
            <input v-model="form.driver.city" class="rf-input" placeholder="Şehir *" required />
            <input v-model="form.driver.occupation" class="rf-input" placeholder="Meslek" />
            <input v-model="form.driver.monthly_income" type="number" class="rf-input" placeholder="Aylık gelir (₺)" />
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input v-model="form.identity.identity_verified" type="checkbox" />
              Kimlik doğrulandı
            </label>
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input v-model="form.identity.phone_verified" type="checkbox" />
              Telefon doğrulandı
            </label>
          </div>

          <div v-else-if="step === 2" class="grid gap-4 md:grid-cols-2">
            <input v-model="form.driver.license_number" class="rf-input" placeholder="Ehliyet No *" required />
            <input v-model="form.driver.license_class" class="rf-input" placeholder="Sınıf (B)" />
            <input v-model="form.license.license_issue_date" type="date" class="rf-input" required />
            <input v-model.number="form.license.license_points" type="number" class="rf-input" placeholder="Ceza puanı" />
            <input v-model.number="form.license.license_penalty_count" type="number" class="rf-input" placeholder="Ceza sayısı" />
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input v-model="form.license.has_src_certificate" type="checkbox" />
              SRC belgesi var
            </label>
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input v-model="form.license.has_psychotechnical" type="checkbox" />
              Psikoteknik raporu var
            </label>
          </div>

          <div v-else class="grid gap-4 md:grid-cols-2">
            <input v-model="form.financial.findeks_score" type="number" class="rf-input" placeholder="Findeks skoru" />
            <input v-model.number="form.financial.payment_delay_count" type="number" class="rf-input" placeholder="Ödeme gecikme sayısı" />
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input v-model="form.financial.has_enforcement_record" type="checkbox" />
              İcra kaydı var
            </label>
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input v-model="form.financial.bank_blacklist_flag" type="checkbox" />
              Banka kara listesi
            </label>
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input v-model="form.financial.fraud_suspicion" type="checkbox" />
              Dolandırıcılık şüphesi
            </label>
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input v-model="form.identity.document_fraud_suspicion" type="checkbox" />
              Belge sahteciliği şüphesi
            </label>
          </div>

          <div class="mt-6 flex justify-between gap-3">
            <button v-if="step > 1" type="button" class="rf-btn-ghost" @click="step -= 1">Geri</button>
            <div class="ml-auto flex gap-3">
              <button v-if="step < 3" type="button" class="rf-btn-primary" :disabled="!canGoNext" @click="step += 1">İleri</button>
              <button v-else type="button" class="rf-btn-primary" :disabled="loading" @click="submit">
                {{ loading ? 'Kaydediliyor…' : 'Kaydet ve Değerlendir' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
