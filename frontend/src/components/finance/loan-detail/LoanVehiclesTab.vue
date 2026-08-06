<script setup>
// Kredi Araç Listesi — bu krediye bağlı araç tahsisleri (LoanVehicleAllocation),
// salt okunur rapor. Ekleme/kaldırma yok; veri zaten Excel'den içe aktarılan
// gerçek eşleştirmeden geliyor (reseed_vehicle_loans).
import { computed } from 'vue'
import LoanDataTable from './LoanDataTable.vue'
import { useUiStore } from '../../../stores/uiStore.js'
import { formatTL } from '../../../utils/format.js'

const props = defineProps({
  loan: { type: Object, required: true },
})

const ui = useUiStore()

const loanLabel = computed(() => props.loan.loan_no || props.loan.lender_name || '—')

const rows = computed(() =>
  (props.loan.vehicle_allocations ?? []).map((a) => ({
    ...a,
    vehicle_label: `${a.brand ?? ''} ${a.model_name ?? ''}`.trim(),
    loan_label: loanLabel.value,
  })),
)

const columns = [
  { key: 'plate_number', label: 'Araç', align: 'left', formatter: (row) => row.plate_number },
  { key: 'vehicle_label', label: 'Marka / Model', align: 'left' },
  { key: 'loan_label', label: 'Kredi Adı', align: 'left' },
  { key: 'purchase_price', label: 'Satın Alma Fiyatı', align: 'right', formatter: (row) => row.purchase_price != null ? formatTL(row.purchase_price, { decimals: true }) : '—' },
  { key: 'financed_amount', label: 'Bu Krediyle Finanse Edilen', align: 'right', formatter: (row) => formatTL(row.financed_amount, { decimals: true }) },
]

function goToVehicle(row) {
  ui.openVehicleDetail(row.vehicle)
}
</script>

<template>
  <LoanDataTable
    :rows="rows"
    :columns="columns"
    :search-keys="['plate_number', 'vehicle_label']"
    date-filter-key="created_at"
    storage-key="vehicles"
  >
    <template #row-extra="{ row }">
      <button
        type="button"
        class="text-xs font-bold text-brand-600 hover:text-brand-800"
        @click="goToVehicle(row)"
      >
        Detay →
      </button>
    </template>
  </LoanDataTable>
</template>
