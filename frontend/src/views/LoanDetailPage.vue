<script setup>
import { ref } from 'vue'
import LoanDetailSidebar from '../components/finance/loan-detail/LoanDetailSidebar.vue'
import LoanInstallmentsTab from '../components/finance/loan-detail/LoanInstallmentsTab.vue'
import LoanVehiclesTab from '../components/finance/loan-detail/LoanVehiclesTab.vue'
import { formatTL, formatDate, formatPercent } from '../utils/format.js'

defineProps({
  loan: { type: Object, default: null },
})
const emit = defineEmits(['close'])

const activeTab = ref('installments')
</script>

<template>
  <div v-if="loan">
    <button
      type="button"
      class="mb-5 flex items-center gap-2 text-sm font-bold text-slate-600 hover:text-slate-900"
      @click="emit('close')"
    >
      <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
      </svg>
      <span class="underline underline-offset-2">Tüm Kredilere Dön</span>
    </button>

    <div class="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 class="text-2xl font-black text-slate-900">{{ loan.loan_no || loan.lender_name || 'Kredi' }}</h1>
        <p v-if="loan.loan_no && loan.lender_name" class="mt-0.5 text-sm text-slate-500">{{ loan.lender_name }}</p>
      </div>
      <dl class="flex flex-wrap gap-6 text-sm">
        <div>
          <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Anapara</dt>
          <dd class="font-bold text-slate-800">{{ formatTL(loan.principal_amount) }}</dd>
        </div>
        <div>
          <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Aylık Faiz</dt>
          <dd class="font-bold text-slate-800">{{ formatPercent(Number(loan.monthly_interest_rate) * 100) }}</dd>
        </div>
        <div>
          <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Vade</dt>
          <dd class="font-bold text-slate-800">{{ loan.term_months }} ay</dd>
        </div>
        <div>
          <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Başlangıç</dt>
          <dd class="font-bold text-slate-800">{{ formatDate(loan.start_date) }}</dd>
        </div>
        <div>
          <dt class="text-xs font-bold uppercase tracking-wide text-slate-400">Bitiş</dt>
          <dd class="font-bold text-slate-800">{{ loan.end_date ? formatDate(loan.end_date) : '—' }}</dd>
        </div>
      </dl>
    </div>

    <div class="flex gap-6">
      <LoanDetailSidebar :active-tab="activeTab" @select="activeTab = $event" />

      <div class="min-w-0 flex-1">
        <LoanInstallmentsTab v-if="activeTab === 'installments'" :loan="loan" />
        <LoanVehiclesTab v-else-if="activeTab === 'vehicles'" :loan="loan" />
      </div>
    </div>
  </div>

  <div v-else class="grid h-full place-items-center">
    <div class="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-brand-600"></div>
  </div>
</template>
