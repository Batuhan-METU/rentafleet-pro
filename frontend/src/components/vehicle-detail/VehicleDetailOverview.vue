<script setup>
import { computed, onMounted, ref } from "vue";
import { useAuthStore } from "../../stores/authStore.js";
import { useFinanceStore } from "../../stores/financeStore.js";
import { formatDate, formatDateShort, formatTL, formatKm } from "../../utils/format.js";
import { accruedInsuranceByTypeForYear } from "../../utils/insuranceAccrual.js";
import { ICON_PATHS } from "../../utils/iconPaths.js";
import VehicleOperationalExpenseModal from "./VehicleOperationalExpenseModal.vue";

const props = defineProps({
  vehicle: { type: Object, required: true },
});
const emit = defineEmits(["edit", "switch-tab"]);

const auth = useAuthStore();
const finance = useFinanceStore();
const summaryLoading = ref(false);
const showOperationalModal = ref(false);

const FUEL = {
  GASOLINE: "Benzin",
  DIESEL: "Dizel",
  LPG: "LPG",
  HYBRID: "Hibrit",
  ELECTRIC: "Elektrik",
};

// --- İkon yolları (heroicons outline, tek <path> içinde çoklu alt-yol) ---
const ICONS = {
  chassis:
    "M15 9h3.75M15 12h3.75M15 15h3.75M4.5 19.5h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5zm6-10.125a1.875 1.875 0 11-3.75 0 1.875 1.875 0 013.75 0zm1.294 6.336a6.721 6.721 0 01-3.17.789 6.721 6.721 0 01-3.168-.789 3.376 3.376 0 016.338 0z",
  plate:
    "M3.75 6.75h16.5a1.5 1.5 0 011.5 1.5v7.5a1.5 1.5 0 01-1.5 1.5H3.75a1.5 1.5 0 01-1.5-1.5v-7.5a1.5 1.5 0 011.5-1.5zM6.75 10.5h3m3.75 0h4.5m-8.25 3h4.5",
  brand:
    "M9.568 3H5.25A2.25 2.25 0 003 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 005.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 009.568 3zM6.375 7.125a.75.75 0 100-1.5.75.75 0 000 1.5z",
  model: ICON_PATHS.truck,
  package:
    "M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-9v9",
  calendar: ICON_PATHS.calendar,
  gauge:
    "M12 21a9 9 0 100-18 9 9 0 000 18z M12 12l3.5-3.5 M12 3v1.5 M21 12h-1.5 M12 21v-1.5 M3 12h1.5",
  fuel: "M4.5 3.75h6v16.5h-6a1.5 1.5 0 01-1.5-1.5V5.25a1.5 1.5 0 011.5-1.5zM10.5 8.25h3l3 3v7.5a1.5 1.5 0 01-1.5 1.5h-1.5m0-15v3.75a1.5 1.5 0 001.5 1.5h1.5",
  cash: "M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  droplet:
    "M12 3c-3.5 4-6 7.373-6 10.5A6 6 0 0012 20a6 6 0 006-6.5C18 10.373 15.5 7 12 3z",
  trending: ICON_PATHS.trendingUp,
  banknote:
    "M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0018.75 4.5H5.25A2.25 2.25 0 003 6.75v10.5A2.25 2.25 0 005.25 19.5z",
  scale:
    "M12 3v17.25m0 0c-1.472 0-2.882.265-4.185.75M12 20.25c1.472 0 2.882.265 4.185.75M18.75 4.97A48.416 48.416 0 0012 4.5c-2.291 0-4.545.16-6.75.47m13.5 0c1.01.143 2.01.317 3 .52m-3-.52l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.988 5.988 0 01-2.031.352 5.988 5.988 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L18.75 4.971zm-16.5.52c.99-.203 1.99-.377 3-.52m0 0l2.62 10.726c.122.499-.106 1.028-.589 1.202a5.989 5.989 0 01-2.031.352 5.989 5.989 0 01-2.031-.352c-.483-.174-.711-.703-.59-1.202L5.25 4.971z",
  clipboard:
    "M9 12.75h6m-6 3h6m1.5 5.25H7.5a2.25 2.25 0 01-2.25-2.25V5.25A2.25 2.25 0 017.5 3h4.879a1.5 1.5 0 011.06.44l4.122 4.12a1.5 1.5 0 01.44 1.061v9.129a2.25 2.25 0 01-2.25 2.25z",
  shield: ICON_PATHS.shieldCheck,
  chart:
    "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z",
  info: "M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z",
  bank: "M12 21v-8.25M15.75 21v-8.25M8.25 21v-8.25M3 9l9-6 9 6M3 21h18M4.5 21V9.75M19.5 21V9.75",
};

const vehicleInfoCards = computed(() => {
  const v = props.vehicle;
  const km = formatKm(v.current_km);
  return [
    { icon: "chassis", label: "Şasi Numarası", value: v.chassis_number || "—" },
    { icon: "plate", label: "Plaka", value: v.plate_number || "—" },
    { icon: "brand", label: "Marka", value: v.brand || "—" },
    { icon: "model", label: "Model", value: v.model || "—" },
    { icon: "package", label: "Donanım Paketi", value: v.package || "—" },
    { icon: "calendar", label: "Model Yılı", value: v.production_year || "—" },
    { icon: "gauge", label: "Kilometre", value: km, mono: true },
    {
      icon: "fuel",
      label: "Yakıt Cinsi",
      value: FUEL[v.fuel_type] ?? v.fuel_type ?? "—",
    },
    {
      icon: "cash",
      label: "Satın Alma Fiyatı",
      value: v.purchase_price
        ? formatTL(v.purchase_price, { decimals: true })
        : "—",
      mono: true,
    },
    {
      icon: "calendar",
      label: "Satın Alma (Fatura) Tarihi",
      value: formatDateShort(v.purchase_invoice_date),
    },
    {
      icon: "bank",
      label: "Finansman Tipi",
      value: v.financing_type_display || "—",
    },
    {
      icon: "droplet",
      label: "Yakıt Kapasitesi",
      value: v.fuel_tank_capacity_liters
        ? `${v.fuel_tank_capacity_liters} lt`
        : "—",
    },
  ];
});

// --- Gelir & Gider Özeti -------------------------------------------------
// Ana sayfadaki yıl seçiciyle aynı mantık: toplamlar SEÇİLİ YILA göre
// değişir (build_vehicle_yearly_summary) — ömür-boyu (lifetime) birikmiş
// rakamlar DEĞİL. "Finansman" sekmesi ayrı kalır, hâlâ lifetime gösterir.
const selectedYear = ref(new Date().getFullYear());
const insurancePolicies = computed(() =>
  finance.insurancePoliciesFor(props.vehicle.id),
);
const yearlySummary = computed(() => finance.yearlySummaryFor(props.vehicle.id));
const availableYears = computed(
  () => yearlySummary.value?.available_years ?? [selectedYear.value],
);
const costBreakdown = computed(() => yearlySummary.value?.cost_breakdown ?? null);
const isCurrentYear = computed(() => selectedYear.value === new Date().getFullYear());

// Gelir iki AYRI kaynaktan gelir: kiralama (RentalIncome) ve operasyon
// gider kayıtlarına bağlı geri kazanım/tahsilat (income_amount, ör. sigorta
// tazminatı) — "Gelir Kompozisyonu" bu ikisini ayrı ayrı gösterir, toplamı
// üstteki "Toplam Gelir" kutusuyla BİREBİR aynı olmalı (bkz. Operasyon
// gider kırılımı modalındaki eşdeğer düzeltme — iki yerde ayrı hesaplanan
// aynı rakam zamanla birbirinden sapmasın diye tek kaynak: backend).
const rentalIncome = computed(() => Number(yearlySummary.value?.total_income ?? 0));
const operatingIncome = computed(() => Number(yearlySummary.value?.operating_income ?? 0));
const totalIncome = computed(() => rentalIncome.value + operatingIncome.value);

// §1.5 — bileşen backend'den null geliyorsa (o araç için gerçekten
// uygulanamaz ya da veri eksik) burada da null kalır, sessizce 0'a
// düşürülmez; sadece TOPLAMA girerken (aşağıda) 0 katkı sayılır.
const operatingExpense = computed(() =>
  Number(costBreakdown.value?.operating_expense ?? 0),
);
const insuranceCostAccrued = computed(() =>
  costBreakdown.value?.insurance_cost != null
    ? Number(costBreakdown.value.insurance_cost)
    : null,
);
const creditCostAccrued = computed(() =>
  costBreakdown.value?.credit_cost != null
    ? Number(costBreakdown.value.credit_cost)
    : null,
);
const cashOpportunityCostAccrued = computed(() =>
  costBreakdown.value?.cash_opportunity_cost != null
    ? Number(costBreakdown.value.cash_opportunity_cost)
    : null,
);
const overheadShareAccrued = computed(() =>
  costBreakdown.value?.overhead_share != null
    ? Number(costBreakdown.value.overhead_share)
    : null,
);
// Nakit fırsat maliyeti vadesi dolmuşsa TOPLAM (yukarıdaki tahakkuk) büyük
// kalır ama GÜNCEL GÜNLÜK MALİYET'e artık katkısı sıfırdır — bu ikisi
// arasındaki büyük farkın açıklaması olmadan kafa karıştırıcı görünür,
// bu yüzden burada da (Finansman sekmesindekiyle aynı mantıkla) belirtilir.
const cashOpportunityTermEndDate = computed(
  () => costBreakdown.value?.cash_opportunity_term_end_date ?? null,
);
const isCashOpportunityMatured = computed(
  () =>
    cashOpportunityTermEndDate.value != null &&
    new Date() >= new Date(cashOpportunityTermEndDate.value),
);
// Finansman = kredi payı + nakit fırsat maliyeti + genel gider payı — üçü de
// GENEL_GIDER_HESAPLAMA_KREDI_NAKIT_KARMA.md'nin "3 gider kalemi" (Finansman/
// Sigorta/Operasyon) yapısına uygun olarak tek segmentte toplanır; genel
// gider ayrı bir üst segment değil, finansmanın bir alt kalemidir.
const financingCost = computed(
  () =>
    (creditCostAccrued.value ?? 0) +
    (cashOpportunityCostAccrued.value ?? 0) +
    (overheadShareAccrued.value ?? 0),
);

const totalExpenseKnown = computed(() => costBreakdown.value?.total_cost != null);
const totalExpense = computed(() => {
  if (costBreakdown.value?.total_cost != null) return Number(costBreakdown.value.total_cost);
  return operatingExpense.value + (insuranceCostAccrued.value ?? 0) + financingCost.value;
});
const netTotal = computed(() => totalIncome.value - totalExpense.value);

// §4 — seçili yılın SONUNDAKİ (ya da bugünkü) hibrit günlük maliyet oranı —
// backend'in build_hybrid_daily_cost'unun aynen farklı as_of ile çağrılmış
// hâli, totalların yanında gösterilir.
const dailyCost = computed(() => {
  const value = yearlySummary.value?.daily_cost;
  return value != null ? Number(value) : null;
});

// Poliçe tipine göre TAHAKKUK EDEN sigorta tutarı — insurance_cost_service.
// accrued_insurance_for_vehicle (§3.4) ile BİREBİR aynı formül, paylaşılan
// utils/insuranceAccrual.js'ten ("Poliçeler" sekmesiyle AYNI fonksiyon —
// iki yerde ayrı yazılmış aynı hesap zamanla birbirinden sapmasın diye).
const insuranceByType = computed(() =>
  accruedInsuranceByTypeForYear(insurancePolicies.value, selectedYear.value),
);

// Gider kompozisyon çubuğu — FYS'nin "3 kutu yan yana" ızgarası yerine tek
// çubuk + kırılım listesi (bkz. plan §2, ui-ux-pro-max chart rehberi: ≤5
// segment için pasta yerine daha erişilebilir bir yığılmış çubuk önerir).
const compositionSegments = computed(() => [
  {
    key: "operations",
    label: "Operasyon",
    amount: operatingExpense.value,
    bar: "bg-blue-500",
    chip: "bg-blue-50 text-blue-600",
    icon: "clipboard",
    tab: null,
    action: "operational-modal",
  },
  {
    key: "insurance",
    label: "Sigorta/Kasko",
    amount: insuranceCostAccrued.value ?? 0,
    bar: "bg-yellow-400",
    chip: "bg-yellow-50 text-yellow-600",
    icon: "shield",
    tab: "insurance-policies",
    action: "tab",
  },
  {
    key: "financing",
    label: "Finansman",
    amount: financingCost.value,
    bar: "bg-purple-500",
    chip: "bg-purple-50 text-purple-600",
    icon: "chart",
    tab: "financing",
    action: "tab",
  },
]);

// Gelir kompozisyonu — Gider Kompozisyonu ile AYNI görsel dil (tek çubuk +
// kırılım listesi), gelirin nereden geldiğini açıkça gösterir. "Kiralama"
// tıklanınca Kira/Rezervasyonları sekmesine, "Operasyon" tıklanınca aynı
// Operasyon Gider Kırılımı modalına gider (o modal zaten hem geliri hem
// gideri gösteriyor).
const incomeCompositionSegments = computed(() => [
  {
    key: "rental",
    label: "Kiralama",
    amount: rentalIncome.value,
    bar: "bg-emerald-500",
    chip: "bg-emerald-50 text-emerald-600",
    icon: "banknote",
    tab: "rentals",
    action: "tab",
  },
  {
    key: "operations-income",
    label: "Operasyon",
    amount: operatingIncome.value,
    bar: "bg-teal-500",
    chip: "bg-teal-50 text-teal-600",
    icon: "clipboard",
    tab: null,
    action: "operational-modal",
  },
]);

function incomeShare(value) {
  if (!totalIncome.value) return 0;
  return (value / totalIncome.value) * 100;
}

function expenseShare(value) {
  if (!totalExpense.value) return 0;
  return (value / totalExpense.value) * 100;
}

function signed(value) {
  return `${value >= 0 ? "+" : ""}${formatTL(value, { decimals: true })}`;
}

function onSegmentClick(segment) {
  if (segment.action === "operational-modal") {
    showOperationalModal.value = true;
  } else if (segment.tab) {
    emit("switch-tab", segment.tab);
  }
}

async function loadSummaryData() {
  summaryLoading.value = true;
  try {
    const [, summary] = await Promise.all([
      finance.fetchInsurancePolicies(props.vehicle.id),
      finance.fetchYearlySummary(props.vehicle.id, selectedYear.value),
    ]);
    if (summary?.year) selectedYear.value = summary.year;
  } finally {
    summaryLoading.value = false;
  }
}

async function selectYear(year) {
  if (year === selectedYear.value) return;
  selectedYear.value = year;
  summaryLoading.value = true;
  try {
    await finance.fetchYearlySummary(props.vehicle.id, year);
  } finally {
    summaryLoading.value = false;
  }
}

onMounted(() => {
  if (auth.isFleetManager) void loadSummaryData();
});
</script>

<template>
  <div class="space-y-8">
    <div class="flex items-center justify-between">
      <div>
        <p class="text-sm text-slate-600">
          {{ vehicle.brand }} {{ vehicle.model }}
        </p>
        <p v-if="vehicle.package" class="text-xs text-slate-400">
          {{ vehicle.package }}
        </p>
      </div>
      <button
        v-if="auth.isFleetManager"
        type="button"
        class="rf-btn-secondary"
        @click="emit('edit', vehicle)"
      >
        Düzenle
      </button>
    </div>

    <!-- Araç Bilgileri -->
    <section>
      <h3 class="flex items-center gap-2 text-xl font-black text-slate-900">
        <svg
          class="h-6 w-6 text-rose-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          stroke-width="1.8"
        >
          <path stroke-linecap="round" stroke-linejoin="round" :d="ICONS.info" />
        </svg>
        Araç Bilgileri
      </h3>
      <div class="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div
          v-for="card in vehicleInfoCards"
          :key="card.label"
          class="group rounded-2xl border border-slate-200 bg-white p-4 transition-colors hover:border-slate-300"
        >
          <div class="flex items-center gap-2.5">
            <span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-slate-50 text-slate-400 group-hover:bg-brand-50 group-hover:text-brand-600">
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" :d="ICONS[card.icon]" />
              </svg>
            </span>
            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">{{ card.label }}</p>
          </div>
          <p
            class="mt-2.5 truncate text-lg font-bold text-slate-900"
            :class="{ 'font-mono tabular-nums': card.mono }"
            :title="String(card.value)"
          >
            {{ card.value }}
          </p>
        </div>
      </div>
      <p v-if="vehicle.sipp_detail" class="mt-3 text-xs text-slate-500">
        {{ vehicle.sipp_detail }}
      </p>
    </section>

    <!-- Gelir & Gider Özeti -->
    <section v-if="auth.isFleetManager">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <h3 class="flex items-center gap-2 text-xl font-black text-slate-900">
          <svg
            class="h-6 w-6 text-rose-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.8"
          >
            <path stroke-linecap="round" stroke-linejoin="round" :d="ICONS.trending" />
          </svg>
          Gelir &amp; Gider Özeti
        </h3>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="y in availableYears"
            :key="y"
            type="button"
            class="cursor-pointer rounded-lg px-3 py-1.5 text-xs font-bold tabular-nums transition-all duration-200"
            :class="y === selectedYear
              ? 'bg-gradient-to-r from-rose-600 to-orange-500 text-white shadow-sm'
              : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:ring-rose-300 hover:text-rose-700'"
            :disabled="summaryLoading"
            @click="selectYear(y)"
          >
            {{ y }}
          </button>
        </div>
      </div>
      <p v-if="isCurrentYear && !summaryLoading" class="mt-1.5 text-xs text-slate-400">
        {{ selectedYear }} henüz tamamlanmadı — rakamlar bugüne kadarki tahakkuku gösterir.
      </p>

      <div v-if="summaryLoading" class="mt-4 py-8 text-center text-sm text-slate-400">
        Yükleniyor…
      </div>
      <template v-else>
        <!-- Kompakt istatistik şeridi -->
        <div class="mt-4 grid grid-cols-1 divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white sm:grid-cols-4 sm:divide-x sm:divide-y-0">
          <div class="p-4">
            <p class="text-xs font-bold uppercase tracking-wide text-slate-400">Toplam Gelir</p>
            <p class="mt-1 font-mono text-2xl font-bold tabular-nums text-emerald-600">
              {{ formatTL(totalIncome, { decimals: true }) }}
            </p>
          </div>
          <div class="p-4">
            <p class="text-xs font-bold uppercase tracking-wide text-slate-400">Toplam Gider</p>
            <p v-if="totalExpenseKnown" class="mt-1 font-mono text-2xl font-bold tabular-nums text-rose-600">
              {{ formatTL(totalExpense, { decimals: true }) }}
            </p>
            <p v-else class="mt-1 text-sm font-semibold text-slate-400">Veri eksik</p>
          </div>
          <div class="p-4">
            <p class="text-xs font-bold uppercase tracking-wide text-slate-400">Net</p>
            <p
              v-if="totalExpenseKnown"
              class="mt-1 font-mono text-2xl font-bold tabular-nums"
              :class="netTotal >= 0 ? 'text-emerald-600' : 'text-rose-600'"
            >
              {{ signed(netTotal) }}
            </p>
            <p v-else class="mt-1 text-sm font-semibold text-slate-400">Veri eksik</p>
          </div>
          <div class="p-4">
            <p class="text-xs font-bold uppercase tracking-wide text-slate-400">Güncel Günlük Maliyet</p>
            <p v-if="dailyCost != null" class="mt-1 font-mono text-2xl font-bold tabular-nums text-slate-800">
              {{ formatTL(dailyCost, { decimals: true }) }}
            </p>
            <p v-else class="mt-1 text-sm font-semibold text-slate-400">Veri eksik</p>
          </div>
        </div>

        <!-- Gelir kompozisyonu: gelirin nereden geldiği, Gider Kompozisyonu ile aynı dil -->
        <div class="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
          <div class="flex items-center justify-between">
            <p class="text-sm font-bold text-slate-800">Gelir Kompozisyonu</p>
            <p class="font-mono text-sm font-bold tabular-nums text-slate-900">
              {{ formatTL(totalIncome, { decimals: true }) }}
            </p>
          </div>

          <div v-if="totalIncome > 0" class="mt-3 flex h-2.5 overflow-hidden rounded-full bg-slate-100">
            <div
              v-for="segment in incomeCompositionSegments"
              :key="segment.key"
              :class="segment.bar"
              class="h-full transition-all first:rounded-l-full last:rounded-r-full"
              :style="{ width: incomeShare(segment.amount) + '%' }"
              :title="`${segment.label}: %${incomeShare(segment.amount).toFixed(0)}`"
            />
          </div>
          <div v-else class="mt-3 h-2.5 rounded-full bg-slate-100" />

          <ul class="mt-4 divide-y divide-slate-100">
            <li v-for="segment in incomeCompositionSegments" :key="segment.key">
              <button
                type="button"
                class="flex w-full items-center gap-3 py-2.5 text-left transition-colors hover:bg-slate-50"
                @click="onSegmentClick(segment)"
              >
                <span :class="segment.chip" class="grid h-8 w-8 shrink-0 place-items-center rounded-lg">
                  <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round" :d="ICONS[segment.icon]" />
                  </svg>
                </span>
                <span class="min-w-0 flex-1">
                  <span class="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
                    <span class="h-2.5 w-2.5 shrink-0 rounded-full" :class="segment.bar"></span>
                    {{ segment.label }}
                  </span>
                  <span class="block text-xs text-slate-400">%{{ incomeShare(segment.amount).toFixed(0) }} pay</span>
                </span>
                <span class="font-mono text-sm font-bold tabular-nums text-slate-900">
                  {{ formatTL(segment.amount, { decimals: true }) }}
                </span>
                <svg class="h-4 w-4 shrink-0 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </button>
            </li>
          </ul>
        </div>

        <!-- Gider kompozisyonu: tek yığılmış çubuk + kırılım listesi -->
        <div class="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
          <div class="flex items-center justify-between">
            <p class="text-sm font-bold text-slate-800">Gider Kompozisyonu</p>
            <p v-if="totalExpenseKnown" class="font-mono text-sm font-bold tabular-nums text-slate-900">
              {{ formatTL(totalExpense, { decimals: true }) }}
            </p>
            <p v-else class="text-xs font-semibold text-slate-400">Bazı bileşenler eksik — kısmi toplam</p>
          </div>

          <div v-if="totalExpense > 0" class="mt-3 flex h-2.5 overflow-hidden rounded-full bg-slate-100">
            <div
              v-for="segment in compositionSegments"
              :key="segment.key"
              :class="segment.bar"
              class="h-full transition-all first:rounded-l-full last:rounded-r-full"
              :style="{ width: expenseShare(segment.amount) + '%' }"
              :title="`${segment.label}: %${expenseShare(segment.amount).toFixed(0)}`"
            />
          </div>
          <div v-else class="mt-3 h-2.5 rounded-full bg-slate-100" />

          <ul class="mt-4 divide-y divide-slate-100">
            <li v-for="segment in compositionSegments" :key="segment.key">
              <component
                :is="segment.action === 'none' ? 'div' : 'button'"
                :type="segment.action === 'none' ? undefined : 'button'"
                class="flex w-full items-center gap-3 py-2.5 text-left transition-colors"
                :class="segment.action === 'none' ? '' : 'hover:bg-slate-50'"
                @click="segment.action === 'none' ? null : onSegmentClick(segment)"
              >
                <span :class="segment.chip" class="grid h-8 w-8 shrink-0 place-items-center rounded-lg">
                  <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round" :d="ICONS[segment.icon]" />
                  </svg>
                </span>
                <span class="min-w-0 flex-1">
                  <span class="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
                    <span class="h-2.5 w-2.5 shrink-0 rounded-full" :class="segment.bar"></span>
                    {{ segment.label }}
                  </span>
                  <span class="block text-xs text-slate-400">%{{ expenseShare(segment.amount).toFixed(0) }} pay</span>
                </span>
                <span class="font-mono text-sm font-bold tabular-nums text-slate-900">
                  {{ formatTL(segment.amount, { decimals: true }) }}
                </span>
                <svg v-if="segment.action !== 'none'" class="h-4 w-4 shrink-0 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
                </svg>
              </component>
              <!-- Sigorta alt kırılımı: tahakkuk (TAM prim değil) -->
              <div v-if="segment.key === 'insurance' && insuranceCostAccrued" class="ml-11 mb-2 space-y-1 text-xs text-slate-400">
                <div class="flex justify-between"><span>Trafik Sigortası (tahakkuk)</span><span class="font-mono tabular-nums">{{ formatTL(insuranceByType.LIABILITY, { decimals: true }) }}</span></div>
                <div class="flex justify-between"><span>Kasko Sigortası (tahakkuk)</span><span class="font-mono tabular-nums">{{ formatTL(insuranceByType.COMPREHENSIVE, { decimals: true }) }}</span></div>
                <div class="flex justify-between"><span>Yeşil Kart Sigortası (tahakkuk)</span><span class="font-mono tabular-nums">{{ formatTL(insuranceByType.GREEN_CARD, { decimals: true }) }}</span></div>
              </div>
              <!-- Finansman alt kırılımı: yalnızca uygulanabilir olan(lar). Her
                   satır AÇIKÇA "bu aracın payı" — kredinin/genel giderin
                   TAMAMI değil (bkz. GENEL_GIDER_HESAPLAMA_KREDI_NAKIT_
                   KARMA.md §10 madde 1: en sık karıştırılan nokta budur). -->
              <div v-if="segment.key === 'financing' && (creditCostAccrued != null || cashOpportunityCostAccrued != null || overheadShareAccrued != null)" class="ml-11 mb-2 space-y-1 text-xs text-slate-400">
                <div v-if="creditCostAccrued != null" class="flex justify-between"><span>Kredi Faizi — bu aracın payı (tahakkuk, kredinin tamamı değil)</span><span class="font-mono tabular-nums">{{ formatTL(creditCostAccrued, { decimals: true }) }}</span></div>
                <div v-if="cashOpportunityCostAccrued != null" class="flex justify-between"><span>Nakit Fırsat Maliyeti — bu aracın payı (tahakkuk)</span><span class="font-mono tabular-nums">{{ formatTL(cashOpportunityCostAccrued, { decimals: true }) }}</span></div>
                <div v-if="isCashOpportunityMatured" class="rounded-lg bg-slate-50 px-2 py-1.5 text-[11px] text-slate-500">
                  Nakit fırsat maliyeti vadesi ({{ formatDate(cashOpportunityTermEndDate) }}) doldu — bu yüzden yukarıdaki tutar artık büyümüyor ve "Güncel Günlük Maliyet"e katkısı sıfır; toplam gider yine de bu tarihe kadar birikmiş olanı gösterir.
                </div>
                <div v-if="overheadShareAccrued != null" class="flex justify-between"><span>Genel Gider Payı — bu aracın payı (tahakkuk)</span><span class="font-mono tabular-nums">{{ formatTL(overheadShareAccrued, { decimals: true }) }}</span></div>
              </div>
            </li>
          </ul>
        </div>
      </template>
    </section>
  </div>

  <VehicleOperationalExpenseModal
    v-if="showOperationalModal"
    :vehicle-id="vehicle.id"
    :year="selectedYear"
    @close="showOperationalModal = false"
  />
</template>
