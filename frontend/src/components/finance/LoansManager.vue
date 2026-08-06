<script setup>
// Krediler sayfası — kredi tanımları (§3.1). Taksit planı ve araç tahsisleri
// artık burada değil, satıra tıklayınca açılan Kredi Detay sayfasında
// (LoanDetailPage.vue) gösteriliyor.
import { onMounted, ref } from 'vue'
import { useLoanStore } from '../../stores/loanStore.js'
import { useUiStore } from '../../stores/uiStore.js'
import { formatTL, formatDate, formatPercent } from '../../utils/format.js'
import LoanFormModal from './LoanFormModal.vue'
import bankIcon from '../icons/1052854.png'

const loanStore = useLoanStore()
const ui = useUiStore()

const showFormModal = ref(false)

onMounted(async () => {
  await loanStore.fetchLoans()
})

function openCreate() {
  showFormModal.value = true
}

function onSaved() {
  showFormModal.value = false
}

async function removeLoan(loan) {
  if (!window.confirm(`"${loan.loan_no || loan.lender_name || 'Kredi'}" silinsin mi? Bağlı araç tahsisleri de silinir.`)) return
  await loanStore.deleteLoan(loan.id)
}

function openDetail(loan) {
  ui.openLoanDetail(loan.id)
}
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-lg font-black text-slate-900">Krediler</h2>
        <p class="text-sm text-slate-500">Araç filosunu finanse eden kredi tanımları.</p>
      </div>
      <button type="button" class="rf-btn-primary" @click="openCreate">
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
        </svg>
        Kredi Ekle
      </button>
    </div>

    <p v-if="loanStore.error" class="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-700">
      {{ typeof loanStore.error === 'string' ? loanStore.error : 'Bir hata oluştu.' }}
    </p>

    <div v-if="loanStore.loading && !loanStore.loans.length" class="py-16 text-center text-sm text-slate-400">
      Yükleniyor…
    </div>

    <div v-else-if="!loanStore.loans.length" class="rf-glass rounded-3xl border border-dashed border-white/50 px-4 py-10 text-center text-sm text-slate-500">
      Henüz kredi kaydı yok.
    </div>

    <div v-else class="overflow-hidden rounded-2xl border border-slate-200 bg-white">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-400">
          <tr>
            <th class="px-4 py-3 text-left">Kredi</th>
            <th class="px-4 py-3 text-right">Anapara</th>
            <th class="px-4 py-3 text-right">Aylık Faiz</th>
            <th class="px-4 py-3 text-right">Vade</th>
            <th class="px-4 py-3 text-left">Başlangıç</th>
            <th class="px-4 py-3 text-left">Bitiş Tarihi</th>
            <th class="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="loan in loanStore.loans"
            :key="loan.id"
            role="button"
            tabindex="0"
            class="group cursor-pointer border-t border-slate-100 transition-colors duration-150 hover:bg-slate-50 focus:bg-slate-50 focus:outline-none"
            @click="openDetail(loan)"
            @keydown.enter="openDetail(loan)"
            @keydown.space.prevent="openDetail(loan)"
          >
            <td class="px-4 py-3">
              <div class="flex items-center gap-3">
                <div class="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-slate-900/[0.04]">
                  <img :src="bankIcon" alt="" class="h-6 w-6 object-contain" />
                </div>
                <div>
                  <p class="font-bold text-slate-900">{{ loan.loan_no || loan.lender_name || '—' }}</p>
                  <p v-if="loan.loan_no && loan.lender_name" class="text-xs text-slate-500">{{ loan.lender_name }}</p>
                </div>
              </div>
            </td>
            <td class="px-4 py-3 text-right">{{ formatTL(loan.principal_amount) }}</td>
            <td class="px-4 py-3 text-right">{{ formatPercent(Number(loan.monthly_interest_rate) * 100) }}</td>
            <td class="px-4 py-3 text-right">{{ loan.term_months }} ay</td>
            <td class="px-4 py-3 text-slate-500">{{ formatDate(loan.start_date) }}</td>
            <td class="px-4 py-3 text-slate-500">{{ loan.end_date ? formatDate(loan.end_date) : '—' }}</td>
            <td class="px-4 py-3 text-right">
              <div class="flex items-center justify-end gap-3 text-xs">
                <span class="font-bold text-brand-600 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                  Detaylar →
                </span>
                <button type="button" class="font-semibold text-red-600" @click.stop="removeLoan(loan)">Sil</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <LoanFormModal
      v-if="showFormModal"
      @close="showFormModal = false"
      @saved="onSaved"
    />
  </div>
</template>
