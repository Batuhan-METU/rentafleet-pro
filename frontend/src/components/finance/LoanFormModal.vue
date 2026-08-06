<script setup>
// Kredi ekleme/düzenleme modalı (§3.1). Faiz oranları kullanıcıya yüzde
// olarak gösterilir (ör. "3.5"), backend'e ondalık olarak (0.035) gönderilir.
import { reactive, ref } from 'vue'
import { useLoanStore } from '../../stores/loanStore.js'
import { useModalLifecycle } from '../../composables/useModalLifecycle.js'
import DatePicker from '../vehicle-form/DatePicker.vue'

const emit = defineEmits(['close', 'saved'])

const loanStore = useLoanStore()

const form = reactive({
  loan_no: '',
  lender_name: '',
  principal_amount: '',
  monthly_interest_rate_percent: '',
  term_months: 36,
  start_date: '',
  end_date: '',
  bsmv_rate_percent: '',
  notes: '',
})

const submitting = ref(false)
const errorMsg = ref('')

useModalLifecycle(() => emit('close'))

async function submit() {
  errorMsg.value = ''
  if (!form.principal_amount || !form.monthly_interest_rate_percent || !form.term_months || !form.start_date) {
    errorMsg.value = 'Anapara, aylık faiz oranı, vade ve başlangıç tarihi zorunludur.'
    return
  }
  submitting.value = true
  try {
    const payload = {
      loan_no: form.loan_no.trim(),
      lender_name: form.lender_name.trim(),
      principal_amount: form.principal_amount,
      monthly_interest_rate: Number(form.monthly_interest_rate_percent) / 100,
      term_months: Number(form.term_months),
      start_date: form.start_date,
      end_date: form.end_date || undefined,
      bsmv_rate: form.bsmv_rate_percent === '' ? undefined : Number(form.bsmv_rate_percent) / 100,
      notes: form.notes.trim(),
    }
    const saved = await loanStore.createLoan(payload)
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
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <div class="absolute inset-0 bg-slate-900/50" aria-hidden="true" @click="emit('close')" />

      <div
        class="relative z-10 flex max-h-[min(90vh,100dvh-2rem)] w-full max-w-xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl"
        role="dialog"
        aria-modal="true"
      >
        <header class="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-6 py-4">
          <h2 class="text-lg font-semibold leading-tight text-slate-900">
            Yeni Kredi
          </h2>
          <button
            type="button"
            class="shrink-0 rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Kapat"
            @click="emit('close')"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <form class="flex-1 space-y-4 overflow-y-auto px-6 py-5" @submit.prevent="submit">
          <div class="grid grid-cols-2 gap-4">
            <label class="block">
              <span class="mb-1 block text-xs font-medium text-slate-500">Kredi No (opsiyonel)</span>
              <input v-model="form.loan_no" class="rf-input" placeholder="BURGAN-55.000.000" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-medium text-slate-500">Banka / Kurum</span>
              <input v-model="form.lender_name" class="rf-input" placeholder="Ziraat Bankası" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-medium text-slate-500">Anapara (TL) *</span>
              <input v-model="form.principal_amount" type="number" class="rf-input" placeholder="1000000" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-medium text-slate-500">Aylık Faiz Oranı (%) *</span>
              <input
                v-model="form.monthly_interest_rate_percent"
                type="number"
                step="0.01"
                class="rf-input"
                placeholder="3.5"
              />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-medium text-slate-500">Vade (ay) *</span>
              <input v-model="form.term_months" type="number" class="rf-input" placeholder="36" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-medium text-slate-500">Başlangıç Tarihi *</span>
              <DatePicker v-model="form.start_date" />
            </label>
            <label class="block">
              <span class="mb-1 block text-xs font-medium text-slate-500">Bitiş Tarihi (opsiyonel)</span>
              <DatePicker v-model="form.end_date" />
            </label>
            <label class="block col-span-2">
              <span class="mb-1 block text-xs font-medium text-slate-500">BSMV Oranı (%)</span>
              <input
                v-model="form.bsmv_rate_percent"
                type="number"
                step="0.01"
                class="rf-input"
                placeholder="Boş bırakılırsa şirket varsayılanı kullanılır (%5)"
              />
            </label>
          </div>

          <label class="block">
            <span class="mb-1 block text-xs font-medium text-slate-500">Notlar</span>
            <textarea v-model="form.notes" rows="2" class="rf-input resize-none" />
          </label>

          <p v-if="errorMsg" class="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
            {{ errorMsg }}
          </p>
        </form>

        <footer class="flex shrink-0 items-center justify-end gap-3 border-t border-slate-200 px-6 py-4">
          <button
            type="button"
            class="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
            @click="emit('close')"
          >
            İptal
          </button>
          <button type="button" :disabled="submitting" class="rf-btn-primary" @click="submit">
            Kredi Ekle
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
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
</style>
