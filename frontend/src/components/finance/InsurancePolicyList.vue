<script setup>
// Araç sigorta/kasko poliçeleri (§3.4) — salt okunur, "Poliçeler" sekmesine
// gömülü. Poliçe girişi artık BURADAN değil, araç ekleme/düzenleme
// sihirbazından yapılıyor (bkz. vehicle-form/StepFinancingInsurance.vue).
import { computed, onMounted, ref } from 'vue'
import { useFinanceStore } from '../../stores/financeStore.js'
import { formatDate, formatTL } from '../../utils/format.js'
import { accruedInsuranceByTypeForYear } from '../../utils/insuranceAccrual.js'

const props = defineProps({
  vehicleId: { type: Number, required: true },
})
const emit = defineEmits(['edit'])

const finance = useFinanceStore()
const loading = ref(false)

const POLICY_TYPES = [
  { value: 'LIABILITY', label: 'Trafik Sigortası' },
  { value: 'COMPREHENSIVE', label: 'Kasko' },
  { value: 'GREEN_CARD', label: 'Yeşil Kart' },
]

const policies = computed(() => finance.insurancePoliciesFor(props.vehicleId))

// Araç Detayı'ndaki "Gelir & Gider Özeti"nde görülen "Sigorta/Kasko"
// tutarı, buradaki TAM yıllık primler değil, o poliçenin İÇİNDE BUGÜNE
// KADAR TAHAKKUK EDEN kısmıdır — ikisi kasıtlı olarak farklı ölçüler, bu
// yüzden karışıklığı önlemek için burada da (aynı paylaşılan fonksiyonla)
// gösterilir.
const currentYear = new Date().getFullYear()
const accruedByType = computed(() => accruedInsuranceByTypeForYear(policies.value, currentYear))

const slots = computed(() =>
  POLICY_TYPES.map((type) => ({
    ...type,
    policy: policies.value.find((p) => p.policy_type === type.value) ?? null,
    accrued: accruedByType.value[type.value] ?? 0,
  })),
)

function progress(policy) {
  const start = new Date(policy.start_date).getTime()
  const end = new Date(policy.end_date).getTime()
  const now = Date.now()
  if (end <= start) return 0
  return Math.min(100, Math.max(0, ((now - start) / (end - start)) * 100))
}

function daysRemaining(policy) {
  const end = new Date(policy.end_date).getTime()
  const days = Math.ceil((end - Date.now()) / (1000 * 60 * 60 * 24))
  return days
}

async function load() {
  loading.value = true
  try {
    await finance.fetchInsurancePolicies(props.vehicleId)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="mb-4 flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3">
      <p class="text-xs text-slate-500">
        Poliçe bilgilerini eklemek veya güncellemek için aracı düzenleyin.
      </p>
      <button
        type="button"
        class="shrink-0 rounded-lg bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white transition hover:bg-slate-700"
        @click="emit('edit')"
      >
        Düzenle
      </button>
    </div>

    <div v-if="loading" class="py-8 text-center text-sm text-slate-400">Yükleniyor…</div>
    <div v-else class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div
        v-for="slot in slots"
        :key="slot.value"
        class="rounded-2xl border border-slate-200 bg-white p-4"
      >
        <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">{{ slot.label }}</p>

        <template v-if="slot.policy">
          <p class="mt-2 font-mono text-xl font-bold tabular-nums text-slate-900">
            {{ formatTL(slot.policy.amount) }}
          </p>
          <p class="text-[10px] text-slate-400">Yıllık Prim (poliçenin tamamı)</p>
          <p class="mt-1 text-xs text-slate-400">
            {{ formatDate(slot.policy.start_date) }} → {{ formatDate(slot.policy.end_date) }}
          </p>
          <div class="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              class="h-full rounded-full"
              :class="daysRemaining(slot.policy) <= 30 ? 'bg-amber-400' : 'bg-brand-500'"
              :style="{ width: progress(slot.policy) + '%' }"
            />
          </div>
          <p class="mt-1.5 text-[11px] text-slate-400">
            <span v-if="daysRemaining(slot.policy) >= 0">{{ daysRemaining(slot.policy) }} gün kaldı</span>
            <span v-else class="font-semibold text-rose-500">Süresi doldu</span>
          </p>
          <div class="mt-2 rounded-lg bg-slate-50 px-2.5 py-1.5">
            <p class="font-mono text-sm font-bold tabular-nums text-slate-700">{{ formatTL(slot.accrued, { decimals: true }) }}</p>
            <p class="text-[10px] text-slate-400">{{ currentYear }} yılında tahakkuk eden (Gelir &amp; Gider Özeti'ndeki tutar)</p>
          </div>
        </template>
        <p v-else class="mt-2 text-sm text-slate-300">Poliçe girilmemiş</p>
      </div>
    </div>
  </div>
</template>
