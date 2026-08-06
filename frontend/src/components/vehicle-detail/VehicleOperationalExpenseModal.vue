<script setup>
import { computed, onMounted, ref } from 'vue'
import { useFinanceStore } from '../../stores/financeStore.js'
import { formatTL } from '../../utils/format.js'
import { useModalLifecycle } from '../../composables/useModalLifecycle.js'

const props = defineProps({
  vehicleId: { type: Number, required: true },
  // Araç Detayı'ndaki "Gelir & Gider Özeti" hangi yılı gösteriyorsa bu da
  // AYNI yılı göstermeli — aksi halde buradaki toplam, oradaki "Operasyon"
  // satırıyla tutarsız görünür (biri seçili yıl, diğeri ömür-boyu olursa).
  year: { type: Number, required: true },
})
const emit = defineEmits(['close'])

const finance = useFinanceStore()
const loading = ref(false)
const expenseCategoryOptions = ref([])

// Sadece SEÇİLİ DÖNEME ait kayıtlar — backend'in build_vehicle_yearly_
// summary'sinin AYNI sınırları: (bir önceki yılın son günü, min(bu yılın
// son günü, bugün)]. Sadece takvim yılına göre filtrelemek YETERLİ DEĞİL —
// içinde bulunduğumuz yıl için, bugünden SONRAKİ tarihli (ileri tarihli)
// kayıtlar backend'de de "henüz tahakkuk etmedi" sayılıp dışarıda
// bırakılıyor; burada aynısı yapılmazsa iki taraf tutarsız görünür.
const periodStartExclusive = computed(() => new Date(props.year - 1, 11, 31))
const periodEnd = computed(() => {
  const yearEnd = new Date(props.year, 11, 31)
  const today = new Date()
  return yearEnd < today ? yearEnd : today
})
const expensesInYear = computed(() =>
  finance.expensesFor(props.vehicleId).filter((e) => {
    const d = new Date(e.expense_date)
    return d > periodStartExclusive.value && d <= periodEnd.value
  }),
)
// Bu döneme girmeyen kayıtlar (başka yıl ya da bugünden ileri tarihli)
// sessizce yok sayılmaz — kaç tanesinin gizlendiği açıkça belirtilir.
const excludedCount = computed(
  () => finance.expensesFor(props.vehicleId).length - expensesInYear.value.length,
)

// "Gelir" burada KİRALAMA geliri DEĞİLDİR (o, Araç Detayı'nın kendi "Toplam
// Gelir" kutusunda zaten gösteriliyor) — bu, operasyon gider satırlarına
// bağlı geri kazanım/tahsilatların (sigorta tazminatı vb.) toplamıdır.
const totalIncome = computed(() =>
  expensesInYear.value.reduce((sum, e) => sum + Number(e.income_amount ?? 0), 0),
)
const totalExpense = computed(() =>
  expensesInYear.value.reduce((sum, e) => sum + Number(e.amount ?? 0), 0),
)
const netTotal = computed(() => totalIncome.value - totalExpense.value)

// Kategori bazlı kırılım — FYS'nin ekranındaki gibi TÜM kategoriler
// listelenir (bu araçta hiç kaydı olmayanlar da 0,00₺ olarak), her satırda
// Gelir (bu gidere bağlı geri kazanım/tahsilat, ör. sigorta tazminatı) /
// Gider / Fark. Gelirin nereden geldiği, o kategoride görülen kaynakların
// listesi olarak satırın altında gösterilir.
const categoryBreakdown = computed(() => {
  const byCategory = new Map()
  for (const opt of expenseCategoryOptions.value) {
    byCategory.set(opt.value, { label: opt.label, gelir: 0, gider: 0, count: 0, sources: new Set() })
  }
  for (const expense of expensesInYear.value) {
    const key = expense.category
    if (!byCategory.has(key)) {
      byCategory.set(key, { label: expense.category_display || key, gelir: 0, gider: 0, count: 0, sources: new Set() })
    }
    const row = byCategory.get(key)
    row.gider += Number(expense.amount ?? 0)
    row.count += 1
    if (expense.income_amount != null) {
      row.gelir += Number(expense.income_amount)
      if (expense.income_source) row.sources.add(expense.income_source)
    }
  }
  return [...byCategory.values()].map((r) => ({
    ...r,
    fark: r.gelir - r.gider,
    sources: [...r.sources],
  }))
})

async function load() {
  loading.value = true
  try {
    const [, categories] = await Promise.all([
      finance.fetchExpenses(props.vehicleId),
      finance.fetchExpenseCategories(),
    ])
    expenseCategoryOptions.value = categories.map((c) => ({ value: c.value, label: c.label }))
  } finally {
    loading.value = false
  }
}

useModalLifecycle(() => emit('close'))

onMounted(() => {
  void load()
})
</script>

<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4" @click.self="emit('close')">
      <div class="absolute inset-0 bg-slate-900/50" />

      <div class="relative z-10 flex max-h-[85vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <header class="flex items-start justify-between border-b border-slate-100 px-6 py-5">
          <div>
            <h2 class="text-xl font-black text-slate-900">Operasyon Gider Kırılımı — {{ year }}</h2>
            <p class="mt-1 text-sm text-slate-500">Tüm operasyon kategorileri, gelir/gider/fark ile ({{ year }} yılı)</p>
            <p v-if="excludedCount > 0" class="mt-1 text-xs text-amber-600">
              {{ excludedCount }} kayıt bu döneme ait olmadığı için (başka yıl veya ileri tarihli) gösterilmiyor.
            </p>
          </div>
          <button
            type="button"
            class="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Kapat"
            @click="emit('close')"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </header>

        <div class="flex-1 overflow-y-auto px-6 py-5">
          <div v-if="loading" class="py-10 text-center text-sm text-slate-400">Yükleniyor…</div>
          <template v-else>
            <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div class="rounded-xl bg-gradient-to-br from-emerald-50 to-white p-4">
                <p class="text-xs font-bold uppercase tracking-wide text-emerald-700">Operasyon Geliri</p>
                <p class="mt-1 font-mono text-lg font-black tabular-nums text-emerald-800">{{ formatTL(totalIncome, { decimals: true }) }}</p>
                <p class="mt-0.5 text-[10px] text-emerald-600">
                  Gider satırlarına bağlı geri kazanım/tahsilat — kiralama geliri DEĞİL
                  (o, Araç Detayı'ndaki "Toplam Gelir" kutusunda)
                </p>
              </div>
              <div class="rounded-xl bg-gradient-to-br from-rose-50 to-white p-4">
                <p class="text-xs font-bold uppercase tracking-wide text-rose-700">Toplam Gider</p>
                <p class="mt-1 font-mono text-lg font-black tabular-nums text-rose-800">{{ formatTL(totalExpense, { decimals: true }) }}</p>
                <p class="mt-0.5 text-[10px] text-rose-600">Araç Detayı'ndaki "Operasyon" tutarıyla aynı ({{ year }} yılı)</p>
              </div>
              <div class="rounded-xl p-4" :class="netTotal >= 0 ? 'bg-gradient-to-br from-emerald-50 to-white' : 'bg-gradient-to-br from-rose-50 to-white'">
                <p class="text-xs font-bold uppercase tracking-wide" :class="netTotal >= 0 ? 'text-emerald-700' : 'text-rose-700'">Fark</p>
                <p class="mt-1 font-mono text-lg font-black tabular-nums" :class="netTotal >= 0 ? 'text-emerald-800' : 'text-rose-800'">
                  {{ netTotal >= 0 ? '+' : '' }}{{ formatTL(netTotal, { decimals: true }) }}
                </p>
              </div>
            </div>

            <div class="mt-6 overflow-hidden rounded-xl border border-slate-100">
              <table class="w-full text-left text-sm">
                <thead>
                  <tr class="bg-slate-50 text-xs font-bold uppercase tracking-wide text-slate-500">
                    <th class="py-2.5 pl-4 pr-3">İsim</th>
                    <th class="py-2.5 pr-3 text-right">Gelir</th>
                    <th class="py-2.5 pr-3 text-right">Gider</th>
                    <th class="py-2.5 pr-4 text-right">Fark</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in categoryBreakdown"
                    :key="row.label"
                    class="border-t border-slate-100"
                  >
                    <td class="py-2.5 pl-4 pr-3 font-semibold text-slate-800">{{ row.label }}</td>
                    <td class="py-2.5 pr-3 text-right">
                      <span class="font-mono font-bold tabular-nums text-emerald-700">{{ formatTL(row.gelir, { decimals: true }) }}</span>
                      <p v-if="row.sources.length" class="text-[10px] text-slate-400">{{ row.sources.join(', ') }}</p>
                    </td>
                    <td class="py-2.5 pr-3 text-right font-mono font-bold tabular-nums text-rose-700">{{ formatTL(row.gider, { decimals: true }) }}</td>
                    <td
                      class="py-2.5 pr-4 text-right font-mono font-bold tabular-nums"
                      :class="row.fark >= 0 ? 'text-emerald-700' : 'text-rose-700'"
                    >
                      {{ row.fark >= 0 ? '+' : '' }}{{ formatTL(row.fark, { decimals: true }) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>
