<script setup>
import { computed, onMounted, ref } from 'vue'
import { useFinanceStore } from '../../stores/financeStore.js'
import { formatDate, formatPercent, formatTL } from '../../utils/format.js'

const props = defineProps({
  vehicleId: { type: Number, required: true },
})

const finance = useFinanceStore()
const loading = ref(false)
const profile = ref(null)

const allocations = computed(() => finance.loanAllocationsFor(props.vehicleId))
const costBreakdown = computed(
  () => finance.costAnalysisFor(props.vehicleId)?.cost_breakdown ?? null,
)

const financingType = computed(() => profile.value?.financing_type ?? null)
const hasCreditPortion = computed(() =>
  financingType.value === 'LOAN' || financingType.value === 'MIXED',
)
const hasCashPortion = computed(() =>
  financingType.value === 'CASH' || financingType.value === 'MIXED',
)

const accruedCreditCost = computed(() => costBreakdown.value?.credit_cost ?? null)
const accruedCashCost = computed(() => costBreakdown.value?.cash_opportunity_cost ?? null)
const accruedOverhead = computed(() => costBreakdown.value?.overhead_share ?? null)
const cashTermEndDate = computed(() => costBreakdown.value?.cash_opportunity_term_end_date ?? null)

// Kredinin kendi vadesiyle bitmesine paralel: nakit fırsat maliyeti de şirket
// ayarındaki varsayılan vade dolunca durur, tahakkuk o tarihte donar.
const isCashOpportunityMatured = computed(
  () => cashTermEndDate.value != null && new Date() >= new Date(cashTermEndDate.value),
)

function sharePct(allocation) {
  const principal = Number(allocation.loan.principal_amount)
  if (!principal) return 0
  return Math.min(100, (Number(allocation.financed_amount) / principal) * 100)
}

// Vadesi tamamen dolmuş bir kredide "tahakkuk eden" = payının TAMAMI — bu
// §1.2'ye göre doğrudur (vade bitince her şey zaten tahakkuk etmiş demektir).
function isLoanMatured(loan) {
  const maturity = new Date(loan.start_date)
  maturity.setMonth(maturity.getMonth() + Number(loan.term_months))
  return new Date() >= maturity
}

async function load() {
  loading.value = true
  try {
    const [, , profileResult] = await Promise.all([
      finance.fetchLoanAllocations(props.vehicleId),
      finance.fetchCostAnalysis(props.vehicleId),
      finance.fetchProfile(props.vehicleId),
    ])
    profile.value = profileResult
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-if="loading" class="py-8 text-center text-sm text-slate-400">Yükleniyor…</div>
  <div v-else class="space-y-8">
    <!-- Krediler -->
    <section>
      <h3 class="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Krediler</h3>

      <div v-if="!hasCreditPortion" class="rf-glass grid place-items-center rounded-3xl p-10 text-center text-slate-500">
        Bu araç krediyle finanse edilmemiş (Nakit).
      </div>
      <div v-else-if="!allocations.length" class="rf-glass grid place-items-center rounded-3xl p-10 text-center text-slate-500">
        Finansman tipi kredili/karma ama bu araca henüz kredi tahsisi girilmemiş.
      </div>
      <template v-else>
        <div v-if="accruedCreditCost != null" class="mb-4 rounded-2xl border border-purple-100 bg-purple-50/40 p-4">
          <p class="text-xs font-bold uppercase tracking-wide text-purple-700">
            Bu Aracın Payına Düşen Tahakkuk Eden Kredi Faizi + BSMV
          </p>
          <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-purple-800">
            {{ formatTL(accruedCreditCost, { decimals: true }) }}
          </p>
          <p class="mt-1 text-[11px] text-purple-600">
            <strong>Bu, kredinin TAMAMI değil</strong> — sadece bu aracın, filoya girdiği günden bugüne kadar, kendi kredi payı (anapara × gün ağırlıklı) üzerinden biriken faiz+BSMV tutarı.
          </p>
        </div>

        <ul class="space-y-3">
          <li
            v-for="allocation in allocations"
            :key="allocation.id"
            class="overflow-hidden rounded-2xl border border-slate-200 bg-white"
          >
            <div class="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
              <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-purple-50 text-purple-600">
                <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6M3 21h18M4.5 21V9.75M19.5 21V9.75" />
                </svg>
              </span>
              <p class="font-bold text-slate-900">{{ allocation.loan.lender_name || 'Banka belirtilmemiş' }}</p>
            </div>

            <div class="mx-4 mt-4 rounded-xl bg-purple-50/60 p-3">
              <div class="flex items-center justify-between">
                <p class="text-xs font-bold uppercase tracking-wide text-purple-700">Bu Araca Tahsis Edilen Kredi Payı (Anapara)</p>
                <p class="font-mono text-lg font-bold tabular-nums text-purple-800">
                  {{ formatTL(allocation.financed_amount, { decimals: true }) }}
                </p>
              </div>
              <div class="mt-2 h-1.5 overflow-hidden rounded-full bg-purple-100">
                <div class="h-full rounded-full bg-purple-500" :style="{ width: sharePct(allocation) + '%' }" />
              </div>
              <p class="mt-1.5 text-[11px] text-purple-600">
                Kredinin toplam anaparasının %{{ sharePct(allocation).toFixed(0) }}'ı bu araca ait
              </p>
            </div>

            <div class="px-4 py-4">
              <p class="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Kredinin Kendisi (bu araç dahil tüm tahsisli araçlar için ortak)
              </p>
              <dl class="grid grid-cols-2 gap-y-3 text-sm sm:grid-cols-4">
                <div>
                  <dt class="text-xs text-slate-400">Toplam Anapara (kredinin tamamı)</dt>
                  <dd class="font-mono font-medium tabular-nums text-slate-800">{{ formatTL(allocation.loan.principal_amount) }}</dd>
                </div>
                <div>
                  <dt class="text-xs text-slate-400">Aylık faiz</dt>
                  <dd class="font-mono font-medium tabular-nums text-slate-800">{{ formatPercent(Number(allocation.loan.monthly_interest_rate) * 100, { digits: 2 }) }}</dd>
                </div>
                <div>
                  <dt class="text-xs text-slate-400">Vade</dt>
                  <dd class="font-medium text-slate-800">{{ allocation.loan.term_months }} ay</dd>
                </div>
                <div>
                  <dt class="text-xs text-slate-400">Başlangıç</dt>
                  <dd class="font-medium text-slate-800">{{ formatDate(allocation.loan.start_date) }}</dd>
                </div>
              </dl>
              <p v-if="isLoanMatured(allocation.loan)" class="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
                Bu kredinin vadesi tamamlandı — tüm taksitler geçmişte olduğu için bu araca düşen faiz+BSMV payının tamamı tahakkuk etmiş durumda.
              </p>
              <p v-if="allocation.loan.notes" class="mt-3 text-xs text-slate-500">{{ allocation.loan.notes }}</p>
            </div>
          </li>
        </ul>
      </template>
    </section>

    <!-- Nakit Fırsat Maliyeti -->
    <section v-if="hasCashPortion">
      <h3 class="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Nakit Fırsat Maliyeti</h3>
      <div class="rounded-2xl border border-blue-100 bg-blue-50/40 p-4">
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <p class="text-xs font-bold uppercase tracking-wide text-blue-700">Nakit ile Finanse Edilen Tutar</p>
            <p class="mt-1 font-mono text-xl font-bold tabular-nums text-blue-800">
              {{ profile?.cash_financed_amount != null ? formatTL(profile.cash_financed_amount, { decimals: true }) : '—' }}
            </p>
          </div>
          <div>
            <p class="text-xs font-bold uppercase tracking-wide text-blue-700">Bugüne Kadar Tahakkuk Eden Fırsat Maliyeti</p>
            <p class="mt-1 font-mono text-xl font-bold tabular-nums text-blue-800">
              {{ accruedCashCost != null ? formatTL(accruedCashCost, { decimals: true }) : '—' }}
            </p>
          </div>
          <div>
            <p class="text-xs font-bold uppercase tracking-wide text-blue-700">Fırsat Maliyeti Vadesi</p>
            <p class="mt-1 font-mono text-xl font-bold tabular-nums text-blue-800">
              {{ cashTermEndDate ? formatDate(cashTermEndDate) : '—' }}
            </p>
          </div>
        </div>
        <p class="mt-3 text-[11px] text-blue-600">
          Bu tutar nakit/özkaynak ile alınan aracın kullandığı sermayenin alternatif maliyetidir (o para bankaya yatırılsaydı kazanılacak faiz) — kredinin kendi vadesiyle bitmesine paralel olarak, şirket ayarındaki varsayılan vade dolana kadar işler, sonrasında durur.
        </p>
        <p v-if="isCashOpportunityMatured" class="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
          Vade ({{ formatDate(cashTermEndDate) }}) doldu — bu tarihten sonra fırsat maliyeti işlemiyor, tahakkuk eden tutar sabitlendi.
        </p>
      </div>
    </section>

    <!-- Genel Gider Payı -->
    <section>
      <h3 class="mb-3 text-sm font-bold uppercase tracking-wide text-slate-500">Genel Gider Payı</h3>
      <div class="rounded-2xl border border-teal-100 bg-teal-50/40 p-4">
        <p class="text-xs font-bold uppercase tracking-wide text-teal-700">Bugüne Kadar Tahakkuk Eden Genel Gider Payı</p>
        <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-teal-800">
          {{ accruedOverhead != null ? formatTL(accruedOverhead, { decimals: true }) : '—' }}
        </p>
        <p class="mt-1 text-[11px] text-teal-600">
          Şirketin araca özel olmayan genel giderlerinin (personel, kira, elektrik/su vb.), filodaki tüm araçlara fiyat-ağırlıklı olarak günlük dağıtılan payı.
        </p>
      </div>
    </section>
  </div>
</template>
