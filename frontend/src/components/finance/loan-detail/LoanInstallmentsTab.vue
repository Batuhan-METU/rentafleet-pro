<script setup>
// Taksit Listesi — LoanInstallment kayıtları (backend'de generate_amortization_schedule
// ile önceden hesaplanmış, salt okunur). KKDF sütunu YOK: kaynak verinin (Taksit_Plani.xlsx)
// ana gövdesinde bulunmuyor, uydurulmayacak.
import { computed } from 'vue'
import LoanDataTable from './LoanDataTable.vue'
import { formatTL, formatDate } from '../../../utils/format.js'

const props = defineProps({
  loan: { type: Object, required: true },
})

const rows = computed(() => props.loan.installments ?? [])

const columns = [
  { key: 'installment_no', label: 'Taksit No', align: 'left' },
  { key: 'due_date', label: 'Taksit Tarihi', align: 'left', formatter: (row) => formatDate(row.due_date) },
  { key: 'total_amount', label: 'Taksit Tutarı', align: 'right', formatter: (row) => formatTL(row.total_amount, { decimals: true }) },
  { key: 'principal_amount', label: 'Anapara', align: 'right', formatter: (row) => formatTL(row.principal_amount, { decimals: true }) },
  { key: 'interest_amount', label: 'Faiz Tutarı', align: 'right', formatter: (row) => formatTL(row.interest_amount, { decimals: true }) },
  { key: 'bsmv_amount', label: 'BSMV', align: 'right', formatter: (row) => formatTL(row.bsmv_amount, { decimals: true }) },
  { key: 'remaining_principal_after', label: 'Kalan Anapara', align: 'right', formatter: (row) => formatTL(row.remaining_principal_after, { decimals: true }) },
]
</script>

<template>
  <LoanDataTable
    :rows="rows"
    :columns="columns"
    :search-keys="['installment_no', 'due_date']"
    date-filter-key="due_date"
    storage-key="installments"
  />
</template>
